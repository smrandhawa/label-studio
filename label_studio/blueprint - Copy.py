import os
import io
import attr
import lxml
import time
import shutil
import flask
import pathlib
import functools
import logging
import logging.config
import pandas as pd
import traceback as tb
import lxml.etree
import label_studio
import flask_login
import click

try:
    import ujson as json
except ModuleNotFoundError:
    import json

# setup default config for logging
with io.open(os.path.join(os.path.dirname(__file__), 'logger.json')) as f:
    logging.config.dictConfig(json.load(f))
import random
from uuid import uuid4
from urllib.parse import unquote
from datetime import datetime
from inspect import currentframe, getframeinfo
from gevent.pywsgi import WSGIServer
from flask import (
    request, jsonify, make_response, Response, Response as HttpResponse,
    send_file, session, redirect, current_app, Blueprint, url_for, g
)
from flask_api import status
from types import SimpleNamespace

from label_studio.utils import uploader
from label_studio.utils.io import find_dir, find_editor_files
from label_studio.utils.validation import TaskValidator
from label_studio.utils.exceptions import ValidationError, LabelStudioError
from label_studio.utils.functions import (
    set_external_hostname, set_web_protocol, get_web_protocol,
    generate_time_series_json, generate_sample_task, get_sample_task
)
from label_studio.utils.misc import (
    exception_handler, exception_handler_page, check_port_in_use, start_browser, str2datetime,
    config_line_stripped, get_config_templates, convert_string_to_hash, serialize_class
)
from label_studio.utils.analytics import Analytics
from label_studio.utils.argparser import parse_input_args
from label_studio.utils.uri_resolver import resolve_task_data_uri
from label_studio.utils.auth import requires_auth
from label_studio.storage import get_storage_form
from label_studio.project import Project
from label_studio.tasks import Tasks
from label_studio.utils.data_manager import prepare_tasks, count_total_user_tasks, get_admin_status
from label_studio.models import User, Completion, Layout, UserScore, Task, BatchData
from label_studio import db
import shapely.geometry as geoShape

INPUT_ARGUMENTS_PATH = pathlib.Path("server.json")

logger = logging.getLogger(__name__)
blueprint = Blueprint(__package__, __name__,
                      static_folder='static', static_url_path='/static',
                      template_folder='templates')
blueprint.add_app_template_filter(str2datetime, 'str2datetime')

def set_input_arguments_path(path):
    global INPUT_ARGUMENTS_PATH
    INPUT_ARGUMENTS_PATH = pathlib.Path(path)

@functools.lru_cache(maxsize=1)
def config_from_file():
    try:
        config_file = INPUT_ARGUMENTS_PATH.open(encoding='utf8')
    except OSError:
        raise LabelStudioError("Can't open input_args file: " + str(INPUT_ARGUMENTS_PATH) + ", "
                               "use set_input_arguments_path() to setup it")

    with config_file:
        data = json.load(config_file)
    return LabelStudioConfig(input_args=SimpleNamespace(**data))


def project_get_or_create(multi_session_force_recreate=False):
    """ Return existed or create new project based on environment. Currently supported methods:
        - "fixed": project is based on "project_name" attribute specified by input args when app starts
        - "session": project is based on "project_name" key restored from flask.session object

        :param multi_session_force_recreate: create a new project if True
        :return: project
    """
    input_args = current_app.label_studio.input_args
    if input_args and input_args.command == 'start-multi-session':
        # get user from session
        if 'user' not in session:
            session['user'] = str(uuid4())
        user = session['user']
        g.user = user

        # get project from session
        if 'project' not in session or multi_session_force_recreate:
            session['project'] = str(uuid4())
        project = session['project']

        # check for shared projects and get owner user
        if project in session.get('shared_projects', []):
            owner = Project.get_user_by_project(project, input_args.root_dir)
            if owner is None:  # owner is None when project doesn't exist
                raise Exception('No such shared project found: project_uuid = ' + project)
            else:
                user = owner

        project_name = user + '/' + project
        return Project.get_or_create(project_name, input_args, context={
            'multi_session': True,
            'user': convert_string_to_hash(user)
        })
    else:
        if multi_session_force_recreate:
            raise NotImplementedError(
                '"multi_session_force_recreate" option supported only with "start-multi-session" mode')
        return Project.get_or_create(input_args.project_name,
                                     input_args, context={'multi_session': False})


@blueprint.before_request
def app_before_request_callback():
    # skip endpoints where no project is needed
    if request.endpoint in ('static', 'send_static'):
        return

    # prepare global variables
    def prepare_globals():
        # setup session cookie
        if 'session_id' not in session:
            session['session_id'] = str(uuid4())
        g.project = project_get_or_create()
        g.analytics = Analytics(current_app.label_studio.input_args, g.project)
        g.sid = g.analytics.server_id

    # show different exception pages for api and other endpoints
    if request.path.startswith('/api'):
        return exception_handler(prepare_globals)()
    else:
        return exception_handler_page(prepare_globals)()


@blueprint.after_request
@exception_handler
def app_after_request_callback(response):
    if hasattr(g, 'analytics'):
        g.analytics.send(request, session, response)
    return response


@blueprint.route('/static/media/<path:path>')
@flask_login.login_required
def send_media(path):
    """ Static for label tool js and css
    """
    media_dir = find_dir('static/media')
    return flask.send_from_directory(media_dir, path)


@blueprint.route('/static/<path:path>')
@flask_login.login_required
def send_static(path):
    """ Static serving
    """
    static_dir = find_dir('static')
    return flask.send_from_directory(static_dir, path)


@blueprint.route('/data/<path:filename>')
@flask_login.login_required
@exception_handler
def get_data_file(filename):
    """ External resource serving
    """
    # support for upload via GUI
    if filename.startswith('upload/'):
        path = os.path.join(g.project.path, filename)
        directory = os.path.abspath(os.path.dirname(path))
        filename = os.path.basename(path)
        return flask.send_from_directory(directory, filename, as_attachment=True)

    # serving files from local storage
    if not g.project.config.get('allow_serving_local_files'):
        raise FileNotFoundError('Serving local files is not allowed. '
                                'Use "allow_serving_local_files": true config option to enable local serving')
    directory = request.args.get('d')
    return flask.send_from_directory(directory, filename, as_attachment=True)


@blueprint.route('/samples/time-series.csv')
@flask_login.login_required
def samples_time_series():
    """ Generate time series example for preview
    """
    time_column = request.args.get('time', '')
    value_columns = request.args.get('values', '').split(',')
    time_format = request.args.get('tf')

    # separator processing
    separator = request.args.get('sep', ',')
    separator = separator.replace('\\t', '\t')
    aliases = {'dot': '.', 'comma': ',', 'tab': '\t', 'space': ' '}
    if separator in aliases:
        separator = aliases[separator]

    # check headless or not
    header = True
    if all(n.isdigit() for n in [time_column] + value_columns):
        header = False

    # generate all columns for headless csv
    if not header:
        max_column_n = max([int(v) for v in value_columns] + [0])
        value_columns = range(1, max_column_n+1)

    ts = generate_time_series_json(time_column, value_columns, time_format)
    csv_data = pd.DataFrame.from_dict(ts).to_csv(index=False, header=header, sep=separator).encode('utf-8')

    mem = io.BytesIO()
    mem.write(csv_data)
    mem.seek(0)
    return send_file(
        mem,
        as_attachment=False,
        attachment_filename='time-series.csv',
        mimetype='text/csv'
    )

""" Reset Completions record of current user for given batchid, used for testing
"""
@blueprint.route('/<batchid>/reset')
@flask_login.login_required
@exception_handler_page
def reset_completion_page(batchid):
    user_id = flask_login.current_user.get_id()
    batch_id = db.session.query(BatchData.id).filter(BatchData.hexID == batchid).scalar()
    if batch_id is None:
        return HttpResponse("<h1> Error: Invalid Batch Id</h1>" )
    userScore = UserScore.query.filter_by(user_id=user_id, batch_id=batch_id).first()
    if userScore is None:
        return HttpResponse("<h1> Error: User Score found! </h1>" )
    userScore.current_task_type = 1
    userScore.score = 0
    db.session.add(userScore)
    db.session.commit()

    db.session.execute(
        'Delete FROM completions where completions.user_id = :userID and completions.batch_id = :batchid ',
        {'userID': user_id, 'batchid': batch_id})
    db.session.commit()
    return HttpResponse("<h1>Completions Reset for " + batchid + " done</h1>")

@blueprint.route('/<batchid>')
@blueprint.route('/', defaults={"batchid": '0'})
# @flask_login.login_required
@exception_handler_page
def labeling_page(batchid = '0'):
    """ Label stream for tasks
        Main landing page for a Job for given batchId
    """
    print('in labelling page')
     # If 'batch id' is empty
    if batchid == '0':
        return redirect(flask.url_for('label_studio.batches_page'))
    # urlParam = ""
    # if g.project.no_tasks():
    #     return redirect(url_for('label_studio.welcome_page'))
    hitId = ""
    turkSubmitTo = ""
    assignmentId = ""
    gameid = ""
    workerId = ""
    setCookie = False

    # get numeric id from hex id
    batch_id = db.session.query(BatchData.id).filter(BatchData.hexID == batchid).scalar()
    if batch_id is None:
        return redirect(flask.url_for('label_studio.invalid_page'))
    else:
        task_data = None
        task_id = request.args.get('task_id', None)
        workerId = request.args.get('workerId', None)

        # Check if user is coming from MTURK or a signed up User

        # check for MTURK as workerId field is provided by amazon
        if workerId is None:

            # check if User is logged in using login screen
            user = flask_login.current_user
            print('printing user')
            print(user)
            if user.is_anonymous or not user.is_authenticated:
                print(' returning here anon')
                return redirect(flask.url_for('label_studio.invalid_page'))
                # redirect(flask.url_for('label_studio.invalid_page'))
            else:
                if user is None:
                    print(' returning here none')
                    return redirect(flask.url_for('label_studio.invalid_page'))
        else:
            # MTruk user
            hitId = request.args.get('hitId', "")
            turkSubmitTo = request.args.get('turkSubmitTo', "")
            assignmentId = request.args.get('assignmentId', "")
            gameid = request.args.get('gameid', "")
            urlParam = "hitId=" + hitId + "/&turkSubmitTo=" + turkSubmitTo + "/&assignmentId=" + assignmentId + "/&gameid=" + gameid
            existing_user = User.query.filter_by(workerId=workerId).first()
            if existing_user is None:
                user = User(
                    workerId=workerId,
                )
                db.session.add(user)
                db.session.commit()
                # db.session.close()
            else:
                user = existing_user

        user_id = user.get_id()
        print(user_id)
        # get user score ( current task type (1-6)) or user score for batch
        userScore = UserScore.query.filter_by(user_id=user_id, batch_id=batch_id).first()
        if userScore is None:
            us = UserScore(user_id=user_id, batch_id=batch_id, score=0, showDemo=False, current_task_type=1)
            db.session.add(us)
            db.session.commit()
            userScore = us

        # check by label_studio guys
        if task_id is not None:
            task_id = int(task_id)
            # Task explore mode
            task_data = g.project.get_task_with_completions(task_id) or g.project.source_storage.get(task_id)
            task_data = resolve_task_data_uri(task_data, project=g.project)

            if g.project.ml_backends_connected:
                task_data = g.project.make_predictions(task_data)
        else:
            # get next Task for user
            print('getting task for user')
            task = g.project.next_task(user_id, userScore.current_task_type, batch_id)
            if task is not None:
                # no tasks found
                Newtask = {}
                Newtask['data'] = task
                Newtask['id'] = task['id']
                db_layout = Layout.query.filter_by(id=task['layout_id']).first()
                Newtask['layout'] = db_layout.data  # task['layout']
                Newtask['description'] = task['description']
                # Newtask['showDemo'] = task['showDemo']
                task = Newtask
                ar = {}
                numOfCompletions = Completion.query.join(Task, Task.id == Completion.task_id).filter(
                    Completion.batch_id == batch_id, Completion.user_id == user_id,
                    Completion.was_skipped == False).count()
                numOfskips = Completion.query.join(Task, Task.id == Completion.task_id).filter(
                    Completion.batch_id == batch_id, Completion.user_id == user_id,
                    Completion.was_skipped == True).count()

                ar = {}
                ar["money"] = "56"
                ar["completed"] = numOfCompletions
                ar["skipped"] = numOfskips
                task["taskAnswerResponse"] = ar
                Newtask['data']['format_type'] = userScore.current_task_type
                task["format_type"] = userScore.current_task_type #Newtask['data']['format_type']
                if 'completions' in Newtask['data']:
                    task["completions"] = Newtask['data']['completions']


                # if "result" in task["data"]:
                # completion = Completion.query.filter_by(user_id=flask_login.current_user.get_id(), task_id=task_id).first()
                # if completion is not None:
                #     completionData = json.loads(task["data"]["result"])
                #     completionData['id'] = 1
                    # logger.debug(json.dumps(json.loads(completion.data), indent=2))
                    # task["completions"] = [completionData]  # [json.loads(completion.data)]

                # task = resolve_task_data_uri(task)

                task = resolve_task_data_uri(task, project=g.project)
            else:
                task = {}
                task['layout'] = g.project.label_config_line
            logger.debug(json.dumps(task, indent=2))
    # print('task_id, task_data and user')
    # print(task_data)
    # print(task_id)
    print(user)
    #print(task)
    resp = make_response(flask.render_template(
        'labeling.html',
        project=g.project,
        config=g.project.config,
        label_config_line=task['layout'],
        task_id=task_id,
        task_data=task_data,
        user=user,
        batchid=batchid,
        hitId=hitId,
        turkSubmitTo=turkSubmitTo,
        assignmentId=assignmentId,
        gameid=gameid,
        workerId=workerId,
        # showDemo=task['showDemo'],
        **find_editor_files()
    ))

    if setCookie:
        resp.set_cookie('utm_source_id', user.workerId)
    return resp

@blueprint.route('/AdminLabeling')
@flask_login.login_required
@exception_handler_page
def admin_labeling_page():
    """ Label stream for tasks
    """
    print('in admin labelling page')
    batchid = request.args.get('batchid', None)
    if batchid == '0':
        return redirect(flask.url_for('label_studio.batches_page'))

    # if g.project.no_tasks():
    #     return redirect(url_for('label_studio.welcome_page'))
    if not flask_login.current_user.is_admin:
        return redirect(flask.url_for('label_studio.not_authorised_page'))


    # task data: load task or task with completions if it exists
    batch_id = db.session.query(BatchData.id).filter(BatchData.hexID == batchid).scalar()
    if batch_id is None:
        return redirect(flask.url_for('label_studio.invalid_page'))
    else:
        task_data = None
        user_id = flask_login.current_user.get_id()

        userScore = UserScore.query.filter_by(user_id=user_id, batch_id=batch_id).first()
        if userScore is None:
            us = UserScore(user_id=user_id, batch_id=batch_id, score=0, showDemo=False, current_task_type=1)
            db.session.add(us)
            db.session

        StepType = userScore.current_task_type

        nextTask = db.session.execute("SELECT * FROM task join completions on task.id == completions.task_id "
                                      "WHERE task.id NOT in (select task_id from completions as cm2 where cm2.user_id =:userID and "
                                      "cm2.batch_id =:batchid ) and task.batch_id = :batchid and task.format_type = :taskType"
                                      " order by RANDOM() LIMIT 1",
        {'userID': user_id, 'batchid': batch_id, 'taskType': 1}).first()

        if nextTask is None:
            nextTask = db.session.execute(
                'SELECT * FROM task WHERE id not in (select task_id from completions '
                'where completions.user_id =:userID and completions.batch_id = :batchid) '
                'and batch_id = :batchid and format_type = :taskType order by random() limit 1',
                {'userID': user_id, 'batchid': batch_id, 'taskType': 1}).first()

        task = nextTask
        if task is not None:
            # no tasks found
            Newtask = {}
            Newtask['data'] = task
            Newtask['id'] = task['id']
            db_layout = Layout.query.filter_by(id=task['layout_id']).first()
            Newtask['layout'] = db_layout.data  # task['layout']
            Newtask['description'] = task['description']
            # Newtask['showDemo'] = task['showDemo']
            task = Newtask
            ar = {}
            numOfCompletions = Completion.query.join(Task, Task.id == Completion.task_id).filter(
                Completion.batch_id == batch_id, Completion.user_id == user_id, Completion.was_skipped == False).count()
            numOfskips = Completion.query.join(Task, Task.id == Completion.task_id).filter(
                Completion.batch_id == batch_id, Completion.user_id == user_id, Completion.was_skipped == True).count()

            ar = {}
            ar["money"] = "56"
            ar["completed"] = numOfCompletions
            ar["skipped"] = numOfskips
            task["taskAnswerResponse"] = ar
            Newtask['data']['format_type'] = StepType
            task["format_type"] = StepType#Newtask['data']['format_type']
            if 'completions' in Newtask['data']:
                task["completions"] = Newtask['data']['completions']


            # if "result" in task["data"]:
            # completion = Completion.query.filter_by(user_id=flask_login.current_user.get_id(), task_id=task_id).first()
            # if completion is not None:
            #     completionData = json.loads(task["data"]["result"])
            #     completionData['id'] = 1
                # logger.debug(json.dumps(json.loads(completion.data), indent=2))
                # task["completions"] = [completionData]  # [json.loads(completion.data)]

            # task = resolve_task_data_uri(task)

            task = resolve_task_data_uri(task, project=g.project)
        else:
            task = {}
            task['layout'] = g.project.label_config_line

        print('check task')
        print(task)
        logger.debug(json.dumps(task, indent=2))
    return flask.render_template(
        'AdminLabeling.html',
        project=g.project,
        config=g.project.config,
        label_config_line=task['layout'],
        # task_id=task_id,
        task_data=task_data,
        user=flask_login.current_user,
        batchid=batchid,
        # showDemo=task['showDemo'],
        **find_editor_files()
    )

@blueprint.route('/welcome')
@flask_login.login_required
@exception_handler_page
def welcome_page():
    """ On-boarding page
    """
    g.project.update_on_boarding_state()
    return flask.render_template(
        'welcome.html',
        config=g.project.config,
        project=g.project,
        on_boarding=g.project.on_boarding,
        user=flask_login.current_user
    )

@blueprint.route('/noAuth')
# @flask_login.login_required
@exception_handler_page
def not_authorised_page():
    return flask.render_template(
        'NoAuth.html',
        config=g.project.config,
        project=g.project,
        on_boarding=g.project.on_boarding,
        user=flask_login.current_user
    )

@blueprint.route('/invalid')
# @flask_login.login_required
@exception_handler_page
def invalid_page():
    return flask.render_template(
        'InvalidPage.html',
        config=g.project.config,
        project=g.project,
        on_boarding=g.project.on_boarding,
        user=flask_login.current_user
    )

@blueprint.route('/batches')
@flask_login.login_required
@exception_handler_page
def batches_page():
    """ On-boarding page
    """

    # is_admin = flask_login.current_user.__getattr__("is_admin")
    batches = db.session.execute("select * from BatchData")
    batches = batches.fetchall()

    return flask.render_template(
        'batches.html',
        batches=batches,
        project=g.project,
        config=g.project.config,
        user=flask_login.current_user
    )

@blueprint.route('/api/PROJECT/batch/delTasks', methods=['POST'])
@flask_login.login_required
@exception_handler_page
def del_Batch_tasks():


    if request.method == 'POST':
        batchid = request.values.get('batchid', '-1')
        if batchid == '-1':
            return make_response(json.dumps({'Error': True, "msg": "Invalid Batch ID"}), 201)

        db.session.execute("delete from task where batch_id = :batchid",
                {'batchid': batchid})
        db.session.commit()
        db.session.execute(
            'Delete FROM completions where completions.user_id = :userID and completions.batch_id = :batchid ',
            {'userID': 0, 'batchid': batchid})
        db.session.commit()
        return make_response(json.dumps({'Error': False, "msg": "Tasks Deleted"}), 201)


@blueprint.route('/tasks', methods=['GET', 'POST'])
@flask_login.login_required
@exception_handler_page
def tasks_page():
    """ Tasks and completions page
    """
    batchid = request.args.get('batchid', None)
    if batchid is None:
        return redirect(flask.url_for('label_studio.invalid_page'))
    batch_id = db.session.query(BatchData.id).filter(BatchData.hexID == batchid).scalar()
    if batch_id is None:
        return redirect(flask.url_for('label_studio.invalid_page'))
    serialized_project = g.project.serialize()
    serialized_project['multi_session_mode'] = current_app.label_studio.input_args.command != 'start-multi-session'
    return flask.render_template(
        'tasks.html',
        config=g.project.config,
        project=g.project,
        serialized_project=serialized_project,
        user=flask_login.current_user,
        batchid=batchid,
        **find_editor_files()
    )


@blueprint.route('/setup')
@flask_login.login_required
@exception_handler_page
def setup_page():
    """ Setup labeling config
    """

    if not flask_login.current_user.is_admin:
        return redirect(flask.url_for('label_studio.not_authorised_page'))

    input_values = {}
    project = g.project
    input_args = current_app.label_studio.input_args

    g.project.description = project.get_config(project.name, input_args).get('description', 'Untitled')

    # evaluate all projects for this user: user_projects + shared_projects
    if project.config.get("show_project_links_in_multisession", True) and hasattr(g, 'user'):
        user = g.user
        project_ids = g.project.get_user_projects(user, input_args.root_dir)

        # own projects
        project_names = [os.path.join(user, uuid) for uuid in project_ids]
        project_desc = [Project.get_config(name, input_args).get('description', 'Untitled') for name in project_names]
        own_projects = dict(zip(project_ids, project_desc))

        # shared projects
        shared_projects = {}
        for uuid in session.get('shared_projects', []):
            tmp_user = Project.get_user_by_project(uuid, input_args.root_dir)
            project_name = os.path.join(tmp_user, uuid)
            project_desc = Project.get_config(project_name, input_args).get('description', 'Untitled')
            shared_projects[uuid] = project_desc
    else:
        own_projects, shared_projects = {}, {}

    # this is useful for the transfer to playground templates
    template_mode = request.args.get('template_mode')
    page = 'includes/setup_templates.html' if template_mode else 'setup.html'

    templates = get_config_templates(g.project.config)
    return flask.render_template(
        page,
        config=g.project.config,
        project=g.project,
        label_config_full=g.project.label_config_full,
        templates=templates,
        input_values=input_values,
        multi_session=input_args.command == 'start-multi-session',
        own_projects=own_projects,
        shared_projects=shared_projects,
        user=flask_login.current_user,
        template_mode=template_mode
    )


@blueprint.route('/import')
@flask_login.login_required
@exception_handler_page
def import_page():
    """ Import tasks from JSON, CSV, ZIP and more
    """
    return flask.render_template(
        'import.html',
        config=g.project.config,
        user=flask_login.current_user,
        project=g.project
    )


@blueprint.route('/Myimport')
@flask_login.login_required
@exception_handler_page
def my_import_page():
    """ Import tasks from JSON, CSV, ZIP and more
    """
    task= {'text': 'ABBA Live is an album of live recordings by Swedish pop group ABBA , released by Polar Music in 1986. A live album was something that many ABBA fans had demanded for several years. ABBA themselves had toyed with the idea on a couple of occasions , but always decided against it. Finally , four years after the members went their separate ways , a live collection was released after all. The resultant album , ABBA Live , contained recordings from 1977 , 1979 and 1981. The tracks were mostly taken from ABBA ’s concerts at Wembley Arena in London in November 1979 , with a few additional songs taken from the tour of Australia in March 1977 and the Dick Cavett Meets ABBA television special , taped in April 1981. When this LP / CD was released , the band \'s popularity was at an all - time low and none of the members themselves were involved in the production of the album. Much to the dismay of both music critics and ABBA fans it also had 80 \'s synth drums overdubbed on most tracks , taking away the true live feeling of the performances. Neither did it feature any of the tracks that the band had performed live on their tours but never included on any of their studio albums , such as " I Am an A " , " Get on the Carousel " , " I \'m Still Alive " , or the original live versions of the songs from the 1977 mini - musical The Girl with the Golden Hair : " Thank You for the Music " , " I Wonder ( Departure ) " and " I \'m a Marionette " , all of which had slightly different lyrics and/or musical arrangements to the subsequent studio recordings included on. Several tracks had also been heavily edited , in the case of the 1979 live recording of " Does Your Mother Know " by as much as five minutes since it originally was performed on that tour as a medley with " Hole in Your Soul ". ABBA Live was the first ABBA album to be simultaneously released on LP and CD , the CD having three " extra tracks ". The album did not perform very well , internationally or domestically , peaking at # 49 in Sweden and only staying in the charts for two weeks. It was remastered and rereleased by Polydor / Polar in 1997 , but is currently out of print.', 'layout_id': 2, 'groundTruth': ' ', 'format_type': 1, 'batch_id': 1, 'description': ' ', 'id': 0}
    # task  = json.loads("x")
    # completion = {'task_id': 35, 'user_id': 0, 'data': '{"lead_time": 3.821, "result": [{"value": {"start": 0, "end": 1, "text": "Polar Music", "labels": ["Organization"]}, "id": "Q930T6M", "from_name": "label", "to_name": "text", "type": "labels"}, {"value": {"start": 0, "end": 1, "text": "Sweden", "labels": ["Location"]}, "id": "QD1WUAX", "from_name": "label", "to_name": "text", "type": "labels"}, {"labels": "P495", "direction": "bi", "from_id": "Q930T6M", "to_id": "QD1WUAX", "type": "relation"}], "user": 0, "created_at": 1616101190}', 'completed_at': '1616127668', 'batch_id': 1, 'was_skipped': 0}
    # completion = {'task_id': 37, 'user_id': 0, 'data': '{"lead_time": 3.821, "result": [{"value": {"start": 81, "end": 92, "text": "Polar Music", "labels": ["Organization"]}, "id": "I1RJK0V", "from_name": "label", "to_name": "text", "type": "labels"}, {"value": {"start": 2003, "end": 2009, "text": "Sweden", "labels": ["Location"]}, "id": "ED155JD", "from_name": "label", "to_name": "text", "type": "labels"}, {"labels": "country of origin", "direction": "bi", "from_id": "I1RJK0V", "to_id": "ED155JD", "type": "relation"}], "user": 0}', 'completed_at': 1616101190, 'batch_id': 1, 'was_skipped': 0}
    # completion = {'task_id': 37, 'user_id': 0, 'data': '{"lead_time": 3.821, "result": [{"value": {"start": 63, "end": 70, "text": "Piraeus", "labels": ["Location"]}, "id": "BAIWKP0", "from_name": "label", "to_name": "text", "type": "labels"}, {"value": {"start": 548, "end": 554, "text": "Greece", "labels": ["Location"]}, "id": "IJYQKAD", "from_name": "label", "to_name": "text", "type": "labels"}, {"labels": ["country"], "direction": "bi", "from_id": "BAIWKP0", "to_id": "IJYQKAD", "type": "relation"}, {"value": {"start": 90, "end": 100, "text": "Skai Group", "labels": ["Organization"]}, "id": "ULZ6X0L", "from_name": "label", "to_name": "text", "type": "labels"}, {"value": {"start": 548, "end": 554, "text": "Greece", "labels": ["Location"]}, "id": "RT3Z1LX", "from_name": "label", "to_name": "text", "type": "labels"}, {"labels": ["country"], "direction": "bi", "from_id": "ULZ6X0L", "to_id": "RT3Z1LX", "type": "relation"}, {"value": {"start": 217, "end": 223, "text": "Athens", "labels": ["Location"]}, "id": "RSUC7EN", "from_name": "label", "to_name": "text", "type": "labels"}, {"value": {"start": 548, "end": 554, "text": "Greece", "labels": ["Location"]}, "id": "H7KFCY4", "from_name": "label", "to_name": "text", "type": "labels"}, {"labels": ["country"], "direction": "bi", "from_id": "RSUC7EN", "to_id": "H7KFCY4", "type": "relation"}, {"value": {"start": 0, "end": 7, "text": "Skai TV", "labels": ["Organization"]}, "id": "OR8M1WN", "from_name": "label", "to_name": "text", "type": "labels"}, {"value": {"start": 63, "end": 70, "text": "Piraeus", "labels": ["Location"]}, "id": "QN82EFF", "from_name": "label", "to_name": "text", "type": "labels"}, {"labels": ["headquarters location"], "direction": "bi", "from_id": "OR8M1WN", "to_id": "QN82EFF", "type": "relation"}, {"value": {"start": 0, "end": 7, "text": "Skai TV", "labels": ["Organization"]}, "id": "R5T0BUC", "from_name": "label", "to_name": "text", "type": "labels"}, {"value": {"start": 90, "end": 100, "text": "Skai Group", "labels": ["Organization"]}, "id": "65YKQ4J", "from_name": "label", "to_name": "text", "type": "labels"}, {"labels": ["owned by"], "direction": "bi", "from_id": "R5T0BUC", "to_id": "65YKQ4J", "type": "relation"}, {"value": {"start": 0, "end": 7, "text": "Skai TV", "labels": ["Organization"]}, "id": "PQ7XL0D", "from_name": "label", "to_name": "text", "type": "labels"}, {"value": {"start": 217, "end": 223, "text": "Athens", "labels": ["Location"]}, "id": "1T2Y8KO", "from_name": "label", "to_name": "text", "type": "labels"}, {"labels": ["headquarters location"], "direction": "bi", "from_id": "PQ7XL0D", "to_id": "1T2Y8KO", "type": "relation"}, {"value": {"start": 0, "end": 7, "text": "Skai TV", "labels": ["Organization"]}, "id": "SBPUJ0F", "from_name": "label", "to_name": "text", "type": "labels"}, {"value": {"start": 548, "end": 554, "text": "Greece", "labels": ["Location"]}, "id": "LACGGY9", "from_name": "label", "to_name": "text", "type": "labels"}, {"labels": ["country"], "direction": "bi", "from_id": "SBPUJ0F", "to_id": "LACGGY9", "type": "relation"}], "user": 0}', 'completed_at': 1616101190, 'batch_id': 1, 'was_skipped': 0}
    completion = {'task_id': 37, 'user_id': 0, 'data': '{"lead_time": 3.821, "result": [{"value": {"start": 63, "end": 70, "text": "Piraeus", "labels": ["Location"]}, "id": "3L6VWCS", "from_name": "label", "to_name": "text", "type": "labels"}, {"value": {"start": 548, "end": 554, "text": "Greece", "labels": ["Location"]}, "id": "BHFODCL", "from_name": "label", "to_name": "text", "type": "labels"}, {"labels": ["country"], "direction": "bi", "from_id": "3L6VWCS", "to_id": "BHFODCL", "type": "relation"}, {"value": {"start": 90, "end": 100, "text": "Skai Group", "labels": ["Organization"]}, "id": "W7HWDJY", "from_name": "label", "to_name": "text", "type": "labels"}, {"labels": ["country"], "direction": "bi", "from_id": "W7HWDJY", "to_id": "BHFODCL", "type": "relation"}, {"value": {"start": 217, "end": 223, "text": "Athens", "labels": ["Location"]}, "id": "S93U28J", "from_name": "label", "to_name": "text", "type": "labels"}, {"labels": ["country"], "direction": "bi", "from_id": "S93U28J", "to_id": "BHFODCL", "type": "relation"}, {"value": {"start": 0, "end": 7, "text": "Skai TV", "labels": ["Organization"]}, "id": "N83BRAV", "from_name": "label", "to_name": "text", "type": "labels"}, {"labels": ["headquarters location"], "direction": "bi", "from_id": "N83BRAV", "to_id": "3L6VWCS", "type": "relation"}, {"labels": ["owned by"], "direction": "bi", "from_id": "N83BRAV", "to_id": "W7HWDJY", "type": "relation"}, {"labels": ["headquarters location"], "direction": "bi", "from_id": "N83BRAV", "to_id": "S93U28J", "type": "relation"}, {"labels": ["country"], "direction": "bi", "from_id": "N83BRAV", "to_id": "BHFODCL", "type": "relation"}], "user": 0}', 'completed_at': 1616101190, 'batch_id': 1, 'was_skipped': 0}

    dbCompletion = Completion(user_id=completion["user_id"], task_id=completion['task_id'], data=completion['data'],
                              completed_at=completion['completed_at'], batch_id=completion['batch_id'],
                              was_skipped=completion['was_skipped'])  # ,hexID=completion["result"][0]['id']
    db.session.add(dbCompletion)
    # db.session.commit()
    # db.session.add(dbtask)
    db.session.commit()

    return make_response('', 404)


@blueprint.route('/importTasks')
@flask_login.login_required
@exception_handler_page
def import_Task_page():
# def import_Task_page():
    """ Import tasks from JSON, CSV, ZIP and more
    """
    if not flask_login.current_user.is_admin:
        return redirect(flask.url_for('label_studio.not_authorised_page'))

    return flask.render_template(
        'importTasks.html',
        config=g.project.config,
        user=flask_login.current_user,
        project=g.project,
    )

@blueprint.route('/export')
@flask_login.login_required
@exception_handler_page
def export_page():
    """ Export page: export completions as JSON or using converters
    """
    return flask.render_template(
        'export.html',
        config=g.project.config,
        formats=g.project.converter.supported_formats,
        user=flask_login.current_user,
        project=g.project
    )


@blueprint.route('/model')
@flask_login.login_required
@exception_handler_page
def model_page():
    """ Machine learning backends page
    """
    if not flask_login.current_user.is_admin:
        return redirect(flask.url_for('label_studio.not_authorised_page'))

    ml_backends = []
    for ml_backend in g.project.ml_backends:
        if ml_backend.connected:
            try:
                ml_backend.sync(g.project)
                training_status = ml_backend.is_training(g.project)
                ml_backend.training_in_progress = training_status['is_training']
                ml_backend.model_version = training_status['model_version']
                ml_backend.is_connected = True
                ml_backend.is_error = False
            except Exception as exc:
                logger.error(str(exc), exc_info=True)
                ml_backend.is_error = True
                try:
                    # try to parse json as the result of @exception_handler
                    ml_backend.error = json.loads(str(exc))
                except ValueError:
                    ml_backend.error = {'detail': "Can't parse exception message from ML Backend"}

        else:
            ml_backend.is_connected = False
        ml_backends.append(ml_backend)
    return flask.render_template(
        'model.html',
        config=g.project.config,
        project=g.project,
        user=flask_login.current_user,
        ml_backends=ml_backends
    )


@blueprint.route('/version')
@flask_login.login_required
@exception_handler
def version():
    """ Show LS backend and LS frontend versions
    """
    lsf = json.load(open(find_dir('static/editor') + '/version.json'))
    ver = {
        'label-studio-frontend': lsf,
        'label-studio-backend': label_studio.__version__
    }
    return make_response(jsonify(ver), 200)


@blueprint.route('/render-label-studio', methods=['GET', 'POST'])
@flask_login.login_required
def api_render_label_studio():
    """ Label studio frontend rendering for iframe
    """
    config = request.args.get('config', request.form.get('config', ''))
    config = unquote(config)
    if not config:
        return make_response('No config in POST', status.HTTP_417_EXPECTATION_FAILED)

    task_data, completions, predictions = get_sample_task(config)

    example_task_data = {
        'id': 42,
        'data': task_data,
        'completions': completions,
        'predictions': predictions,
        'project': g.project.id,
        'created_at': '2019-02-06T14:06:42.000420Z',
        'updated_at': '2019-02-06T14:06:42.000420Z'
    }

    # prepare context for html
    config_line = config_line_stripped(config)
    response = {
        'label_config_line': config_line,
        'task_ser': example_task_data
    }
    response.update(find_editor_files())

    return flask.render_template('render_ls.html', **response)


@blueprint.route('/api/validate-config', methods=['POST'])
@flask_login.login_required
def api_validate_config():
    """ Validate label config via tags schema
    """
    if 'label_config' not in request.form:
        return make_response('No label_config in POST', status.HTTP_417_EXPECTATION_FAILED)
    try:
        g.project.validate_label_config(request.form['label_config'])
    except ValidationError as e:
        return make_response(jsonify({'label_config': e.msg_to_list()}), status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return make_response(jsonify({'label_config': [str(e)]}), status.HTTP_400_BAD_REQUEST)

    return Response(status=status.HTTP_204_NO_CONTENT)


@blueprint.route('/api/import-example', methods=['GET', 'POST'])
@flask_login.login_required
def api_import_example():
    """ Generate upload data example by config only
    """
    # django compatibility
    request.GET = request.args
    request.POST = request.form
    config = request.GET.get('label_config', '')
    if not config:
        config = request.POST.get('label_config', '')
    try:
        g.project.validate_label_config(config)
        task_data, _, _ = get_sample_task(config)
    except (ValueError, ValidationError, lxml.etree.Error, KeyError):
        response = HttpResponse('error while example generating', status=status.HTTP_400_BAD_REQUEST)
    else:
        response = HttpResponse(json.dumps(task_data))
    return response


@blueprint.route('/api/import-example-file')
@flask_login.login_required
def api_import_example_file():
    """ Task examples for import
    """
    request.GET = request.args  # django compatibility

    q = request.GET.get('q', 'json')
    filename = 'sample-' + datetime.now().strftime('%Y-%m-%d-%H-%M')
    try:
        task = generate_sample_task(g.project)
    except (ValueError, ValidationError, lxml.etree.Error):
        return HttpResponse('error while example generating', status=status.HTTP_400_BAD_REQUEST)

    tasks = [task, task]

    if q == 'json':
        filename += '.json'
        output = json.dumps(tasks)

    elif q == 'csv':
        filename += '.csv'
        output = pd.read_json(json.dumps(tasks), orient='records').to_csv(index=False)

    elif q == 'tsv':
        filename += '.tsv'
        output = pd.read_json(json.dumps(tasks), orient='records').to_csv(index=False, sep='\t')

    elif q == 'txt':
        if len(g.project.data_types.keys()) > 1:
            raise ValueError('TXT is unsupported for projects with multiple sources in config')

        filename += '.txt'
        output = ''
        for t in tasks:
            output += list(t.values())[0] + '\n'

    else:
        raise ValueError('Incorrect format ("q") in request')

    if request.GET.get('raw', '0') == '1':
        return HttpResponse(output)

    response = HttpResponse(output)
    response.headers['Content-Disposition'] = 'attachment; filename=%s' % filename
    response.headers['filename'] = filename
    return response


@blueprint.route('/api/project', methods=['POST', 'GET', 'PATCH'])
@flask_login.login_required
@exception_handler
def api_project():
    """ Project properties and create a new for multi-session mode
    """
    code = 200
    input_args = current_app.label_studio.input_args

    # new project
    if request.method == 'POST' and request.args.get('new', False):
        input_args.web_gui_project_desc = request.args.get('desc')
        g.project = project_get_or_create(multi_session_force_recreate=True)
        delattr(input_args, 'web_gui_project_desc')  # remove it to avoid other users affecting
        code = 201

    # update project params, ml backend settings
    elif request.method == 'PATCH':
        g.project.update_params(request.json)
        code = 201

    output = g.project.serialize()
    output['multi_session_mode'] = input_args.command != 'start-multi-session'
    return make_response(jsonify(output), code)


@blueprint.route('/api/project/config', methods=['POST'])
@flask_login.login_required
def api_save_config():
    """ Save labeling config
    """
    label_config = None
    if 'label_config' in request.form:
        label_config = request.form['label_config']
    elif 'label_config' in request.json:
        label_config = request.json['label_config']

    # check config before save
    try:
        g.project.validate_label_config(label_config)
    except ValidationError as e:
        return make_response(jsonify({'label_config': e.msg_to_list()}), status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return make_response(jsonify({'label_config': [str(e)]}), status.HTTP_400_BAD_REQUEST)

    # update config states
    try:
        g.project.update_label_config(label_config)
    except Exception as e:
        return make_response(jsonify({'label_config': [str(e)]}), status.HTTP_400_BAD_REQUEST)

    return Response(status=status.HTTP_201_CREATED)


@blueprint.route('/api/project/import', methods=['POST'])
@flask_login.login_required
@exception_handler
def api_import():
    """ The main API for task import, supports
        * json task data
        * files (as web form, files will be hosted by this flask server)
        * url links to images, audio, csv (if you use TimeSeries in labeling config)
    """
    # make django compatibility for uploader module
    class DjangoRequest:
        def __init__(self): pass
        POST = request.form
        GET = request.args
        FILES = request.files
        data = request.json if request.json else request.form
        content_type = request.content_type

    start = time.time()
    # get tasks from request
    parsed_data, formats = uploader.load_tasks(DjangoRequest(), g.project)
    # validate tasks
    validator = TaskValidator(g.project)
    try:
        new_tasks = validator.to_internal_value(parsed_data)
    except ValidationError as e:
        return make_response(jsonify(e.msg_to_list()), status.HTTP_400_BAD_REQUEST)

    # get the last task id
    max_id_in_old_tasks = -1
    if not g.project.no_tasks():
        max_id_in_old_tasks = g.project.source_storage.max_id()

    new_tasks = Tasks().from_list_of_dicts(new_tasks, max_id_in_old_tasks + 1)
    try:
        g.project.source_storage.set_many(new_tasks.keys(), new_tasks.values())
    except NotImplementedError:
        raise NotImplementedError('Import is not supported for the current storage ' + str(g.project.source_storage))

    # if tasks have completion - we need to implicitly save it to target
    for i in new_tasks.keys():
        for completion in new_tasks[i].get('completions', []):
            g.project.save_completion(int(i), completion)

    # update schemas based on newly uploaded tasks
    g.project.update_derived_input_schema()
    g.project.update_derived_output_schema()

    duration = time.time() - start
    return make_response(jsonify({
        'task_count': len(new_tasks),
        'completion_count': validator.completion_count,
        'prediction_count': validator.prediction_count,
        'duration': duration,
        'formats': formats,
        'new_task_ids': [t for t in new_tasks]
    }), status.HTTP_201_CREATED)


@blueprint.route('/api/project/importTasks', methods=['POST'])
@flask_login.login_required
@exception_handler
def api_task_import():
    """ The main API for task import, supports
        * json task data
        * files (as web form, files will be hosted by this flask server)
        * url links to images, audio, csv (if you use TimeSeries in labeling config)
    """
    # make django compatibility for uploader module
    class DjangoRequest:
        def __init__(self): pass
        POST = request.form
        GET = request.args
        FILES = request.files
        data = request.json if request.json else request.form
        content_type = request.content_type

    start = time.time()
    # get tasks from request
    parsed_data, formats = uploader.load_tasks(DjangoRequest(), g.project)
    # validate tasks
    # validator = TaskValidator(g.project)
    # try:
    #     new_tasks = validator.to_internal_value(parsed_data)
    # except ValidationError as e:
    #     return make_response(jsonify(e.msg_to_list()), status.HTTP_400_BAD_REQUEST)
    new_Task_List = []
    # i = 0
    uploadType = request.args.get('uploadType')
    i = 0
    try:
        if uploadType == "tasks":
            for task in parsed_data:
                task = task["data"]
                dbtask = Task(text=task["text"], layout_id=task["layout_id"], groundTruth=task["groundTruth"],
                              format_type=task["format_type"], batch_id=task["batch_id"], description=task["description"])
                # new_Task_List[i] = dbtask
                i = i + 1
                # new_Task_List.append(dbtask)
                db.session.add(dbtask)
        elif uploadType == "layout":
            for layout in parsed_data:
                i = i + 1
                layout = layout["data"]
                dblayout = Layout(data=layout["data"])
                db.session.add(dblayout)
        elif uploadType == "twc":
            # parsed_data = json.loads(parsed_data)['tasks']
            for task in parsed_data[0]['tasks']:
                i = i + 1
                dbtask = Task(text=task["text"], layout_id=task["layout_id"], groundTruth=task["groundTruth"],
                              format_type=task["format_type"], batch_id=task["batch_id"], description=task["description"])
                db.session.add(dbtask)
                db.session.flush()
                completion = task['completion']
                dbCompletion = Completion(user_id=0, task_id=dbtask.id,
                                          data=completion['data'],
                                          completed_at=completion['completed_at'], batch_id=completion['batch_id'],
                                          was_skipped=completion['was_skipped'])  # ,hexID=completion["result"][0]['id']

                db.session.add(dbCompletion)
        else:
            return make_response("Invalid Type ", status.HTTP_400_BAD_REQUEST)

        db.session.commit()
        duration = time.time() - start
        return make_response(jsonify({
            'task_count': i,
            'duration': duration,
            'formats': uploadType,
        }), status.HTTP_201_CREATED)

    except Exception as exc:
        return make_response(str(exc), status.HTTP_400_BAD_REQUEST)

@blueprint.route('/api/project/export', methods=['GET'])
@flask_login.login_required
@exception_handler
def api_export():
    """ Export labeling results using label-studio-converter to popular formats
    """
    export_format = request.args.get('format')
    now = datetime.now()

    os.makedirs(g.project.export_dir, exist_ok=True)

    zip_dir = os.path.join(g.project.export_dir, now.strftime('%Y-%m-%d-%H-%M-%S'))
    os.makedirs(zip_dir, exist_ok=True)
    g.project.converter.convert(g.project.output_dir, zip_dir, format=export_format)
    shutil.make_archive(zip_dir, 'zip', zip_dir)
    shutil.rmtree(zip_dir)

    zip_dir_full_path = os.path.abspath(zip_dir + '.zip')
    response = send_file(zip_dir_full_path, as_attachment=True)
    response.headers['filename'] = os.path.basename(zip_dir_full_path)
    return response


# @blueprint.route('/api/project/next', defaults={"batchid": '0'}, methods=['GET'])
@blueprint.route('/api/project/next/<batchid>/', methods=['GET'])
# @flask_login.login_required
@exception_handler
def api_generate_next_task(batchid):
    """ Generate next task for labeling page (label stream)
    """
    # try to find task is not presented in completions
    # completed_tasks_ids = g.project.get_completions_ids()
    # task = g.project.next_task(completed_tasks_ids)
    # if batchid == '0':
    #     return make_response('', 404)
    # print(batchid)
    # userId = flask_login.current_user.get_id()

    workerId = request.args.get('workerId', None)
    if workerId is None:
        user = flask_login.current_user
        if user.is_anonymous or not user.is_authenticated:
            workerId = request.cookies.get('utm_source_id')
            if workerId:
                user = User.query.filter_by(workerId=workerId).first()
                if user is None:
                    return make_response('', 404)
            else:
                return make_response('', 404)
        else:
            if user is None:
                return redirect(flask.url_for('label_studio.login'))
    else:
        hitId = request.args.get('hitId', None)
        turkSubmitTo = request.args.get('turkSubmitTo', None)
        assignmentId = request.args.get('assignmentId', None)
        gameid = request.args.get('gameid', None)
        user = User.query.filter_by(workerId=workerId).first()
        if user is None:
            return make_response('', 404)
            # user = User(
            #     workerId=workerId,
            # )
            # db.session.add(user)
            # db.session.commit()
    userId = user.get_id()
    batch_id = db.session.query(BatchData.id).filter(BatchData.hexID == batchid).scalar()
    if batch_id is None:
        return make_response('', 404)
    # traingTask = request.values.get('traingTask', False)
    StepType = db.session.query(UserScore.current_task_type).filter(UserScore.user_id == userId, UserScore.batch_id == batch_id).scalar() # random
    # if user.is_admin:
    #     nextTask = db.session.execute("SELECT *, completions.id as comID FROM task join completions on task.id == completions.task_id "
    #                               "WHERE task.id not in (select task_id from completions as cm2 where cm2.user_id =:userID and "
    #                               "cm2.batch_id =:batchid ) and task.batch_id = :batchid and task.format_type = :taskType"
    #                               " order by RANDOM() LIMIT 1",
    #                               {'userID': userId, 'batchid': batch_id, 'taskType': 1}).first()

    #     print(nextTask)
    #     if nextTask is None:
    #         nextTask = db.session.execute(
    #             'SELECT * FROM task WHERE id not in (select task_id from completions '
    #             'where completions.user_id =:userID and completions.batch_id = :batchid ) '
    #             'and batch_id = :batchid and format_type = :taskType order by random() limit 1',
    #             {'userID': userId, 'batchid': batch_id, 'taskType': 1}).first()

    #     if nextTask is not None:
    #         print('assing dicttask to task')
    #         dictTask = dict(dict(nextTask).items())
    #         print(dictTask)
    #         if "data" in dictTask:
    #             print('assing dicttask to task')
    #             completionData = json.loads(nextTask.data)
    #             print('assing dicttask to task')
    #             completionData['id'] = nextTask["comID"]
    #             # logger.debug(json.dumps(completionData, indent=2))
    #             dictTask["completions"] = [completionData]  # [json.loads(completion.data)]
    #             dictTask['completed_at'] = nextTask.completed_at
    #             dictTask["id"] = dictTask["task_id"]
    #         print('assing dicttask to task')
    #         task = dictTask
    #     else:
    #         task = None
    # else:
    #     task = g.project.next_task(userId, StepType, batch_id)
    print(userId)
    print(StepType)
    print(batch_id)
    task = g.project.next_task(userId, StepType, batch_id)

    if task is None:
        # no tasks found
        return make_response('', 404)

    print('making new task')
    Newtask = {}
    Newtask['data'] = task
    Newtask['id'] = task['id']
    db_layout = Layout.query.filter_by(id=task['layout_id']).first()
    Newtask['layout'] = db_layout.data #task['layout']
    Newtask['description'] = task['description']
    task = Newtask
    Newtask['data']['format_type'] = StepType
    task["format_type"] = StepType #Newtask['data']['format_type']
    if 'completions' in Newtask['data']:
        task["completions"] = Newtask['data']['completions']
        # del(Newtask['data']['completions'])
    # if "result" in task["data"]:
        # completion = Completion.query.filter_by(user_id=flask_login.current_user.get_id(), task_id=task_id).first()
        # if completion is not None:
        # completionData = json.loads(task["data"]["result"])
        # completionData['id'] = 1
        # logger.debug(json.dumps(json.loads(completion.data), indent=2))
        # task["completions"] = [completionData]  # [json.loads(completion.data)]

    print(task)
    ar = {}
    numOfCompletions = Completion.query.join(Task, Task.id == Completion.task_id).filter(
        Completion.batch_id == batch_id, Completion.user_id == userId, Completion.was_skipped == False).count()
    numOfskips = Completion.query.join(Task, Task.id == Completion.task_id).filter(
        Completion.batch_id == batch_id, Completion.user_id == userId, Completion.was_skipped == True).count()

    ar = {}
    ar["money"] = "56"
    ar["completed"] = numOfCompletions
    ar["skipped"] = numOfskips
    task["taskAnswerResponse"] = ar
    # task = resolve_task_data_uri(task)
    print('resolving new task')
    task = resolve_task_data_uri(task, project=g.project)

    # collect prediction from multiple ml backends
    if g.project.ml_backends_connected:
        task = g.project.make_predictions(task)
    logger.debug('Next task:\n' + str(task.get('id', None)))
    logger.debug(json.dumps(task, indent=2))
    return make_response(jsonify(task), 200)


@blueprint.route('/api/project/storage-settings', methods=['GET', 'POST'])
@flask_login.login_required
@exception_handler
def api_project_storage_settings():
    """ Set project storage settings: Amazon S3, Google CS, local file storages.
        Source storages store input tasks in json formats.
        Target storage store completions with labeling results
    """

    # GET: return selected form, populated with current storage parameters
    if request.method == 'GET':
        # render all forms for caching in web
        all_forms = {'source': {}, 'target': {}}
        for storage_for in all_forms:
            for name, description in g.project.get_available_storage_names(storage_for).items():
                current_type = g.project.config.get(storage_for, {'type': ''})['type']
                current = name == current_type
                form_class = get_storage_form(name)
                form = form_class(data=g.project.get_storage(storage_for).get_params()) if current else form_class()
                all_forms[storage_for][name] = {
                    'fields': [serialize_class(field) for field in form],
                    'type': name, 'current': current, 'description': description,
                    'path': getattr(g.project, storage_for + '_storage').readable_path
                }
                # generate data key automatically
                if g.project.data_types.keys():
                    for field in all_forms[storage_for][name]['fields']:
                        if field['name'] == 'data_key' and not field['data']:
                            field['data'] = list(g.project.data_types.keys())[0]
        return make_response(jsonify(all_forms), 200)

    # POST: update storage given filled form
    if request.method == 'POST':
        selected_type = request.args.get('type', '')
        storage_for = request.args.get('storage_for')
        current_type = g.project.config.get(storage_for, {'type': ''})['type']
        selected_type = selected_type if selected_type else current_type

        form = get_storage_form(selected_type)(data=request.json)

        if form.validate_on_submit():
            storage_kwargs = dict(form.data)
            storage_kwargs['type'] = request.json['type']  # storage type
            try:
                g.project.update_storage(storage_for, storage_kwargs)
            except Exception as e:
                traceback = tb.format_exc()
                logger.error(str(traceback))
                return make_response(jsonify({'detail': 'Error while storage update: ' + str(e)}), 400)
            else:
                return make_response(jsonify({'result': 'ok'}), 201)
        else:
            logger.error('Errors: ' + str(form.errors) + ' for request body ' + str(request.json))
            return make_response(jsonify({'errors': form.errors}), 400)


@blueprint.route('/api/project-switch', methods=['GET', 'POST'])
@flask_login.login_required
@exception_handler
def api_project_switch():
    """ Switch projects in multi-session mode
    """
    input_args = current_app.label_studio.input_args

    if request.args.get('uuid') is None:
        return make_response("Not a valid UUID", 400)

    uuid = request.args.get('uuid')
    user = Project.get_user_by_project(uuid, input_args.root_dir)

    # not owner user tries to open shared project
    if user != g.user:
        # create/append shared projects for user
        if 'shared_projects' not in session:
            session['shared_projects'] = {}
        session['shared_projects'].update({uuid: {}})

    # switch project
    session['project'] = uuid

    output = g.project.serialize()
    output['multi_session_mode'] = input_args.command == 'start-multi-session'
    if request.method == 'GET':
        return redirect(url_for('label_studio.setup_page'))
    else:
        return make_response(jsonify(output), 200)

@blueprint.route('/api/user_tasks_count', methods=['GET'])
@flask_login.login_required
@exception_handler
def api_user_tasks_count():
    """ Tasks API: retrieve by filters, delete all tasks
    """
    # retrieve tasks (plus completions and predictions) with pagination & ordering
    if request.method == 'GET':
        batchid = request.values.get('batchid', None)
        # get filter parameters from request
        batch_id = db.session.query(BatchData.id).filter(BatchData.hexID == batchid).scalar()
        if batch_id is None:
            return make_response('', 404)

        print('Getting Tasks count, Here debug by shan, remove print if seen in production')
        params = SimpleNamespace(batchid=batch_id)
        count = count_total_user_tasks(params)
        return make_response(jsonify(str(count)), 200)


@blueprint.route('/api/get_admin_status', methods=['GET'])
@flask_login.login_required
@exception_handler
def api_admin_status():
    """ Tasks API: retrieve by filters, delete all tasks
    """
    # retrieve tasks (plus completions and predictions) with pagination & ordering
    if request.method == 'GET':
        print('Getting admin status, Here debug by shan, remove print if seen in production')
        admin_status = get_admin_status()
        return make_response(jsonify(str(admin_status)), 200)


@blueprint.route('/api/tasks', methods=['GET', 'DELETE'])
@flask_login.login_required
@exception_handler
def api_all_tasks():
    """ Tasks API: retrieve by filters, delete all tasks
    """
    # retrieve tasks (plus completions and predictions) with pagination & ordering
    if request.method == 'GET':
        batchid = request.values.get('batchid', None)
        # get filter parameters from request
        batch_id = db.session.query(BatchData.id).filter(BatchData.hexID == batchid).scalar()
        if batch_id is None:
            return make_response('', 404)

        fields = request.values.get('fields', 'all').split(',')
        page, page_size = int(request.values.get('page', 1)), int(request.values.get('page_size', 10))
        order = request.values.get('order', 'id')
        if page < 1 or page_size < 1:
            return make_response(jsonify({'detail': 'Incorrect page or page_size'}), 422)

        params = SimpleNamespace(batchid=batch_id, fields=fields, page=page, page_size=page_size, order=order)
        tasks = prepare_tasks(g.project, params)
        return make_response(jsonify(tasks), 200)

    # delete all tasks with completions
    if request.method == 'DELETE':
        g.project.delete_tasks()
        return make_response(jsonify({'detail': 'deleted'}), 204)


@blueprint.route('/api/tasks/<task_id>', methods=['GET', 'DELETE'])
@flask_login.login_required
@exception_handler
def api_task_by_id(task_id):
    """ Get task by id, this call will refresh this task predictions
    """

    task_id = int(task_id)

    # try to get task with completions first
    if request.method == 'GET':
        # task_data = g.project.get_task_with_completions(task_id) or g.project.source_storage.get(task_id)
        # task_data = resolve_task_data_uri(task_data, project=g.project)
        task = g.project.source_storage.get(task_id) #project.get_task_with_completions(i)
        completion = Completion.query.filter_by(user_id=flask_login.current_user.get_id(),task_id=task_id).first()
        task = task.__dict__
        task.pop('_sa_instance_state', None)
        if completion is not None:
            completionData = json.loads(completion.data)
            completionData['id'] = completion.id
            # logger.debug(json.dumps(json.loads(completion.data), indent=2))
            task["completions"] = [completionData]#[json.loads(completion.data)]
        task['data'] = {}
        task['data']['text'] = task['text']
        task.pop('text', None)
        UserRanks = []
        ur = {}
        ur["rank"] = 1
        ur["UserName"] = "Bilal Saleem"
        UserRanks.append(ur)
        ur = {}
        ur["rank"] = 2
        ur["UserName"] = "Djelle "
        UserRanks.append(ur)
        ur = {}
        ur["rank"] = 3
        ur["UserName"] = "Shan"
        UserRanks.append(ur)
        task["data"]["userranks"] = UserRanks

        if g.project.ml_backends_connected:
            task = g.project.make_predictions(task)
        logger.debug(json.dumps(task, indent=2))
        # change indent for pretty jsonify
        indent = 2 if request.values.get('pretty', False) else None
        response = current_app.response_class(
            json.dumps(task, indent=indent) + "\n",
            mimetype=current_app.config["JSONIFY_MIMETYPE"],
        )
        return make_response(response, 200)

    # delete task
    elif request.method == 'DELETE':
        g.project.remove_task(task_id)
        return make_response(jsonify('Task deleted.'), 204)


@blueprint.route('/api/tasks/<task_id>/completions', methods=['POST', 'DELETE'])
# @flask_login.login_required
@exception_handler
def api_tasks_completions(task_id):
    """ Save new completion or delete all completions
    """
    task_id = int(task_id)
    # user = flask_login.current_user.get_id()
    workerId = request.args.get('workerId', None)
    if workerId is None:
        user = flask_login.current_user
        if user.is_anonymous or not user.is_authenticated:
            workerId = request.cookies.get('utm_source_id')
            if workerId:
                user = User.query.filter_by(workerId=workerId).first()
                if user is None:
                    return make_response('', 404)
            else:
                return make_response('', 404)
        else:
            if user is None:
                return redirect(flask.url_for('label_studio.login'))
    else:
        hitId = request.args.get('hitId', None)
        turkSubmitTo = request.args.get('turkSubmitTo', None)
        assignmentId = request.args.get('assignmentId', None)
        gameid = request.args.get('gameid', None)
        user = User.query.filter_by(workerId=workerId).first()
        if user is None:
            return make_response('', 404)
            # user = User(
            #     workerId=workerId,
            # )
            # db.session.add(user)
            # db.session.commit()
    userId = user.get_id()
    # if user.is_admin:
    #     userId = 0
    # save completion
    batch_id = db.session.query(Task.batch_id).filter(Task.id==task_id).scalar()
    if request.method == 'POST':
        completion = request.json
        print(completion)
        # cancelled completion
        userScore = UserScore.query.filter_by(user_id=userId, batch_id=batch_id).first()
        was_cancelled = request.values.get('was_cancelled', False)
        print(was_cancelled)
        if was_cancelled:
            completion['was_cancelled'] = True
        else:
            completion.pop('skipped', None)  # deprecated
            completion.pop('was_cancelled', None)
            originalCompletion = Completion.query.filter_by(user_id=0, task_id=task_id).first()
            # evluated = evulateCompletion(completion, originalCompletion, batch_id)
            print(userScore.current_task_type)
            print(completion['result'])
            if userScore.current_task_type == 3 or (userScore.current_task_type in (4, 5, 6) and batch_id == 5):
                originalCompletion = Completion.query.filter_by(user_id=0, task_id=task_id).first()
                data = json.loads(originalCompletion.data)
                #if len(completion['result']) == 0 or len(data['result']) > len(completion['result']):
                if len(completion['result']) == 0:
                    return make_response(json.dumps({'IsEmpty': True, "msg": "Plz complete all tasks"}), 201)
            elif userScore.current_task_type in (4, 5, 6) and len(completion['result']) == 0:
                # originalCompletion = Completion.query.filter_by(user_id=0, task_id=task_id).first()
                # data = json.loads(originalCompletion.data)
                    print('return error')
                    return make_response(json.dumps({'IsEmpty': True, "msg": "Answer response can not be empty"}), 201)
            # elif userScore.current_task_type == 6:
                # originalCompletion = Completion.query.filter_by(user_id=0, task_id=task_id).first()
                # data = json.loads(originalCompletion.data)
                # return make_response(json.dumps({'IsEmpty': True, "msg":""}), 201)
            # userScore = UserScore.query.filter_by(user_id=user, batch_id=batch_id).first()
        print('return before adding completion')
        completion["user"] = userId

        completion_id = g.project.save_completion_in_DB(task_id, completion, batch_id, was_cancelled)

        # checkscore(completion)
        logger.debug("Received completion" + json.dumps(completion, indent=2))
        logger.debug(completion_id)
        if not was_cancelled:
            if userScore is not None:
                if userScore.current_task_type == 1:
                    userScore.current_task_type = 2
                elif userScore.current_task_type == 2:
                    userScore.current_task_type = 3
                elif userScore.current_task_type == 3:
                    numOfCompletions = Completion.query.join(Task, Task.id == Completion.task_id).filter(Completion.batch_id == batch_id, Completion.user_id == userId, Completion.was_skipped == False, Task.format_type == 1).count()
                    if numOfCompletions >= 2:
                        userScore.current_task_type = 4
                elif userScore.current_task_type == 4:
                    # originalCompletion = Completion.query.filter_by(user_id=0, task_id=task_id).first()
                    if evulateCompletion(completion, originalCompletion, batch_id):
                        userScore.score = userScore.score + 10
                    else:
                        userScore.score = userScore.score - 5
                    # numOfCompletions = Completion.query.join(Task, Task.id == Completion.task_id).filter(Completion.batch_id == batch_id, Completion.user_id == userId, Completion.was_skipped == False, Task.format_type == 1).count()
                    # if userScore.score > 40 and numOfCompletions >= 2:
                    if userScore.score > 40:
                        userScore.current_task_type = 5
                elif userScore.current_task_type == 5:
                    rardNum = random.uniform(0, 1)
                    if rardNum >= 0.2:
                        userScore.current_task_type = 5
                    else:
                        userScore.current_task_type = 6
                elif userScore.current_task_type == 6:
                    rardNum = random.uniform(0, 1)
                    if rardNum >=0.2:
                        userScore.current_task_type = 5
                    else:
                        userScore.current_task_type = 6
            else:
                userScore = UserScore(user_id=userId, batch_id=batch_id, score=0, showDemo=False, current_task_type=0)

            db.session.add(userScore)
            db.session.commit()

        # completion_id = g.project.save_completion(task_id, completion)
        return make_response(json.dumps({'id': completion_id}), 201)

    # remove all task completions
    if request.method == 'DELETE':
        if g.project.config.get('allow_delete_completions', False):
            g.project.delete_task_completions(task_id)
            return make_response('deleted', 204)
        else:
            return make_response({'detail': 'Completion removing is not allowed in server config'}, 422)


def evulateCompletion(completion, originalCompletion, batch_id):
    groundTruth = json.loads(originalCompletion.data)
    if batch_id == 1:
        found = 0
        for ur in completion['result']: #us = user response
            for gt in groundTruth['result']: # gt = groundTruth
                if gt['value']['start'] == ur['value']['start'] and gt['value']['end'] == ur['value']['end'] and\
                    gt['value']['text'] == ur['value']['text'] and gt['value']['labels'][0] == ur['value']['labels'][0]:
                    found = found + 1
                    break
        if found/len(groundTruth['result']) >= 0.7:
            return True
        else:
            return False
    elif batch_id == 2:
        iou = 0
        for ur in completion['result']:
            for gt in groundTruth['result']:
                if ur['value']['rectanglelabels'][0] == gt['value']['rectanglelabels'][0]:
                    completionbbox = (
                    ur['value']['x'], ur['value']['y'], ur['value']['width'],
                    ur['value']['height'])
                    completionrect = geoShape.box(*completionbbox, ccw=True)
                    groundTruthbbox = (
                        gt['value']['x'], gt['value']['y'],
                        gt['value']['width'],
                        gt['value']['height'])
                    groundTruthrect = geoShape.box(*groundTruthbbox, ccw=True)
                    if ((completionrect.intersection(groundTruthrect).area) / groundTruthrect.area * 100) >= 50:
                        iou = iou + completionrect.intersection(groundTruthrect).area / completionrect.union(groundTruthrect).area
        if iou / len(groundTruth['result']) >= 0.5:
            return True
        return False
    elif batch_id == 3:
        iou =  0
        for ur in completion['result']:
            for gt in groundTruth['result']:
                if ur['value']['polygonlabels'][0] == gt['value']['polygonlabels'][0]:
                    groundTruthPoly = geoShape.Polygon(ur['value']['points'])
                    completionPoly = geoShape.Polygon(gt['value']['points'])
                    if ((completionPoly.intersection(groundTruthPoly).area)/groundTruthPoly.area * 100) > 50:
                        iou = iou + completionPoly.intersection(groundTruthPoly).area / completionPoly.union(groundTruthPoly).area
        if iou/len(groundTruth['result']) >= 0.5:
            return True
        return False
    elif batch_id == 4:
        found = 0
        for ur in completion['result'][0]['value']['choices']:
            for gt in groundTruth['result'][0]['value']['choices']:
                if gt == ur:
                    found = found + 1
                    break
        if found / len(groundTruth['result'][0]['value']['choices']) >= 0.7:
            return True

        return False
    elif batch_id == 5:
        found = 0
        for ur in completion['result']: #us = user response
            if ur["type"] == "relation":
                for gt in groundTruth['result']: # gt = groundTruth
                    if gt["type"] == "relation":
                        return True

    elif batch_id == 7:
        if len(completion['result'])>0:
            if completion['result'][0]['value']['choices'][0] == groundTruth['result'][0]['value']['choices'][0]:
                return True
            else:
                return False
    return False
@blueprint.route('/api/tasks/<task_id>/completions/<completion_id>', methods=['PATCH', 'DELETE'])
@flask_login.login_required
@exception_handler
def api_completion_by_id(task_id, completion_id):
    """ Update existing completion with patch.
    """
    # catch case when completion is not submitted yet, but user tries to act with it
    if completion_id == 'null':
        return make_response('completion id is null', 200)

    task_id = int(task_id)
    completion_id = int(completion_id)

    # update completion
    if request.method == 'PATCH':
        completion = request.json
        completion['id'] = completion_id
        was_cancelled = 'was_cancelled' in completion
        # if 'was_cancelled' not in completion:
        completion['was_cancelled'] = was_cancelled
        batch_id = db.session.query(Task.batch_id).filter(Task.id == task_id).scalar()
        # g.project.save_completion(task_id, completion)
        # completion['id'] = completion_id
        g.project.save_completion_in_DB(task_id, completion, batch_id, was_cancelled)
        return make_response('ok', 201)

    # delete completion
    elif request.method == 'DELETE':
        if g.project.config.get('allow_delete_completions', False):
            g.project.delete_task_completion(task_id, completion_id)
            return make_response('deleted', 204)
        else:
            return make_response({'detail': 'Completion removing is not allowed in server config'}, 422)


@blueprint.route('/api/completions', methods=['GET', 'DELETE'])
@flask_login.login_required
@exception_handler
def api_all_completions():
    """ Get all completion ids
        Delete all project completions
    """
    # delete all completions
    if request.method == 'DELETE':
        g.project.delete_all_completions()
        return make_response('done', 201)

    # get all completions ids
    elif request.method == 'GET':
        ids = g.project.get_completions_ids()
        return make_response(jsonify({'ids': ids}), 200)

    else:
        return make_response('Incorrect request method', 500)


@blueprint.route('/api/models', methods=['GET', 'DELETE'])
@flask_login.login_required
@exception_handler
def api_models():
    """ List ML backends names and remove it by name
    """
    # list all ml backends
    if request.method == 'GET':
        model_names = [model.model_name for model in g.project.ml_backends]
        return make_response(jsonify({'models': model_names}), 200)

    # delete specified ml backend
    if request.method == 'DELETE':
        ml_backend_name = request.json['name']
        g.project.remove_ml_backend(ml_backend_name)
        return make_response(jsonify('ML backend deleted'), 204)


@blueprint.route('/api/models/train', methods=['POST'])
@flask_login.login_required
@exception_handler
def api_train():
    """ Send train signal to ML backend
    """
    if g.project.ml_backends_connected:
        training_started = g.project.train()
        if training_started:
            logger.debug('Training started.')
            return make_response(jsonify({'details': 'Training started'}), 200)
        else:
            logger.debug('Training failed.')
            return make_response(
                jsonify('Training is not started: seems that you don\'t have any ML backend connected'), 400)
    else:
        return make_response(jsonify("No ML backend"), 400)


@blueprint.route('/api/models/predictions', methods=['GET', 'POST'])
@flask_login.login_required
@exception_handler
def api_predictions():
    """ Make ML predictions using ML backends

        param mode: "data" [default] - task data will be taken and predicted from request.json
                    "all_tasks" - make predictions for all tasks in DB
    """
    mode = request.values.get('mode', 'data')  # data | all_tasks
    if g.project.ml_backends_connected:

        # make prediction for task data from request
        if mode == 'data':
            if request.json is None:
                return make_response(jsonify({'detail': 'no task data found in request json'}), 422)

            task = request.json if 'data' in request.json else {'data': request.json}
            task_with_predictions = g.project.make_predictions(task)
            return make_response(jsonify(task_with_predictions), 200)

        # make prediction for all tasks
        elif mode == 'all_tasks':
            # get tasks ids without predictions
            tasks_with_predictions = {}
            for task_id, task in g.project.source_storage.items():
                task_pred = g.project.make_predictions(task)
                tasks_with_predictions[task_pred['id']] = task_pred

            # save tasks with predictions to storage
            g.project.source_storage.set_many(tasks_with_predictions.keys(), tasks_with_predictions.values())
            return make_response(jsonify({'details': 'predictions are ready'}), 200)

        # unknown mode
        else:
            return make_response(jsonify({'detail': 'unknown mode'}), 422)
    else:
        return make_response(jsonify("No ML backend"), 400)


@blueprint.route('/api/states', methods=['GET'])
@flask_login.login_required
@exception_handler
def stats():
    """ Save states
    """
    return make_response('{"status": "done"}', 200)


@blueprint.route('/api/health', methods=['GET'])
@flask_login.login_required
@exception_handler
def health():
    """ Health check
    """
    return make_response('{"status": "up"}', 200)


@blueprint.errorhandler(ValidationError)
def validation_error_handler(error):
    logger.error(error)
    return str(error), 500


@blueprint.app_template_filter('json')
def json_filter(s):
    return json.dumps(s)


login_manager = flask_login.LoginManager()
def create_app(label_studio_config=None):
    """ Create application factory, as explained here:
        http://flask.pocoo.org/docs/patterns/appfactories/.

    :param label_studio_config: LabelStudioConfig object to use with input_args params
    """
    app = flask.Flask(__package__, static_url_path='')
    app.secret_key = 'A0Zrdqwf1AQWj12ajkhgFN]dddd/,?RfDWQQT'
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.url_map.strict_slashes = False
    app.label_studio = label_studio_config or config_from_file()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    # check LabelStudioConfig correct loading
    if app.label_studio is None:
        raise LabelStudioError('LabelStudioConfig is not loaded correctly')

    app.register_blueprint(blueprint)
    return app

@blueprint.before_app_first_request
def create_tables():
    db.create_all()

@blueprint.route('/signup', methods=['GET', 'POST'])
def signup():
    """
    User sign-up page.

    GET requests serve sign-up page.
    POST requests validate form & user creation.
    """
    if flask.request.method == 'GET':
      return flask.render_template('SignupForm.html')
    else:
        name = request.form['name']
        username = request.form['username']
        password = request.form['password']

        try:
            existing_user = User.query.filter_by(username=username).first()
            if existing_user is None:
                user = User(
                    name=name,
                    username=username,
                )
                user.set_password(password)
                db.session.add(user)
                db.session.commit()  # Create new user
                flask_login.login_user(user)  # Log in as newly created user
                # flash('Signup Done')
                logger.debug("Sign up done")
                return redirect(flask.url_for('label_studio.labeling_page'))
            else:
                logger.debug("Sign up Error1")
                # flash('A user already exists with that username address.')
                return flask.render_template('SignupForm.html')
        except Exception as e:
            # flash('Error.')
            logger.debug("Sign up Error 2")
            logger.debug(e)
            # flash('Error: Try again')
            return flask.render_template('SignupForm.html')

@login_manager.user_loader
def load_user(user_id):
    """Check if user is logged-in on every page load."""
    if user_id is not None:
        return User.query.get(user_id)
    return None


@login_manager.unauthorized_handler
def unauthorized():
    """Redirect unauthorized users to Login page."""
    # flash('You must be logged in to view that page.')
    logger.debug("UnAuthorized access")
    return redirect(flask.url_for('label_studio.login'))

@blueprint.route('/login', methods=['GET', 'POST'])
def login():
    """
    Log-in page for registered users.

    GET requests serve Log-in page.
    POST requests validate and redirect user to dashboard.
    """
    # Bypass if user is logged in
    if flask.request.method == 'GET':
        if flask_login.current_user.is_authenticated:
            return redirect(flask.url_for('label_studio.labeling_page'))
        else:
            return flask.render_template('LoginForm.html')
    else:
    # if flask.request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password=password):
            flask_login.login_user(user)
            return redirect(flask.url_for('label_studio.labeling_page'))
        # flash('Invalid username/password combination')
    return redirect(flask.url_for('label_studio.login'))



@blueprint.route('/logout')
def logout():
    flask_login.logout_user()
    return redirect(flask.url_for('label_studio.login'))

@attr.s(frozen=True)
class LabelStudioConfig:
    input_args = attr.ib()

@blueprint.cli.command("loadtasksold")
@click.argument('input', type=click.File('rb'))
def loadtasksold(input):
    Alltasks = json.loads(input.read())
    # logger.debug(Alltasks)
    from .models import Task
    if len(Alltasks) != 0:
        for i, task in Alltasks.items():
            try:
                dbtask = Task(text=task["data"]["text"], layout=task["data"]["layout"],
                              groundTruth=task["data"]["groundTruth"])
                db.session.add(dbtask)
                db.session.commit()
            except Exception as e:
                logger.debug("Storage db Error 3 ")
                logger.debug(e)

@blueprint.cli.command("loadtasks")
@click.argument('input', type=click.File('rb'))
def loadtasks(input):
    Alltasks = json.loads(input.read())
    # logger.debug(Alltasks)
    from .models import Task
    if len(Alltasks) != 0:
        for task in Alltasks:
            try:
                dbtask = Task(text=task["data"]["text"], layout_id=task["data"]["layout"],
                              groundTruth=task["data"]["groundTruth"])
                db.session.add(dbtask)
                db.session.commit()
            except Exception as e:
                print("Storage db Error 3 ")
                print(e)

@blueprint.cli.command("loadlayout")
@click.argument('input', type=click.File('rb'))
def loadlayout(input):
    layouts = json.loads(input.read())
    # print(layouts)
    # logger.debug(layouts)
    from .models import Task
    if len(layouts) != 0:
        for layout in layouts:
            # text = "test"
            print(layout)
            print(type(layout))
            # print(layouts[0])
            try:
                if "id" in layout and layout["id"] is not None:
                    print("FOUND")
                    db_layout = Layout.query.filter_by(id=layout["id"]).first()
                    if db_layout is not None:
                        db_layout.data = layout["text"]
                        db.session.add(db_layout)
                        db.session.commit()
                    else:
                        db_layout = Layout(data=layout["text"])
                        db.session.add(db_layout)
                        db.session.commit()

                else:
                    db_layout = Layout(data=layout["text"])
                    db.session.add(db_layout)
                    db.session.commit()
            except Exception as e:
                print(e)
                logger.debug("Storage db Error - loadLaout 3 ")
                logger.debug(e)

input_args = parse_input_args()
app = create_app(LabelStudioConfig(input_args=input_args))

login_manager.init_app(app)
login_manager.login_view = 'label_studio.login'
db.init_app(app)


def main():
    # this will avoid looped imports and will register deprecated endpoints in the blueprint
    import label_studio.deprecated
    global app
    global input_args
    # setup logging level
    if input_args.log_level:
        logging.root.setLevel(input_args.log_level)

    # On `init` command, create directory args.project_name with initial project state and exit
    if input_args.command == 'init':
        Project.create_project_dir(input_args.project_name, input_args)
        return

    elif input_args.command == 'start':

        # If `start --init` option is specified, do the same as with `init` command, but continue to run app
        if input_args.init:
            Project.create_project_dir(input_args.project_name, input_args)

        if not os.path.exists(Project.get_project_dir(input_args.project_name, input_args)):
            raise FileNotFoundError(
                'Project directory "{pdir}" not found. '
                'Did you miss create it first with `label-studio init {pdir}` ?'.format(
                    pdir=Project.get_project_dir(input_args.project_name, input_args)))

    # On `start` command, launch browser if --no-browser is not specified and start label studio server
    if input_args.command == 'start':
        import label_studio.utils.functions
        import label_studio.utils.auth
        config = Project.get_config(input_args.project_name, input_args)

        # set username and password
        label_studio.utils.auth.USERNAME = input_args.username or \
            config.get('username') or label_studio.utils.auth.USERNAME
        label_studio.utils.auth.PASSWORD = input_args.password or config.get('password', '')

        # set host name
        host = input_args.host or config.get('host', 'localhost')
        port = input_args.port or config.get('port', 8080)
        server_host = 'localhost' if host == 'localhost' else '0.0.0.0'  # web server host

        # ssl certificate and key
        cert_file = input_args.cert_file or config.get('cert')
        key_file = input_args.key_file or config.get('key')
        ssl_context = None
        if cert_file and key_file:
            config['protocol'] = 'https://'
            ssl_context = (cert_file, key_file)

        # check port is busy
        if not input_args.debug and check_port_in_use('localhost', port):
            old_port = port
            port = int(port) + 1
            print('\n*** WARNING! ***\n* Port ' + str(old_port) + ' is in use.\n' +
                  '* Trying to start at ' + str(port) +
                  '\n****************\n')

        # external hostname is used for data import paths, they must be absolute always,
        # otherwise machine learning backends couldn't access them
        set_web_protocol(input_args.protocol or config.get('protocol', 'http://'))
        external_hostname = get_web_protocol() + host.replace('0.0.0.0', 'localhost')
        if host in ['0.0.0.0', 'localhost', '127.0.0.1']:
            external_hostname += ':' + str(port)
        set_external_hostname(external_hostname)

        start_browser('http://localhost:' + str(port), input_args.no_browser)
        if input_args.use_gevent:
            app.debug = input_args.debug
            ssl_args = {'keyfile': key_file, 'certfile': cert_file} if ssl_context else {}
            http_server = WSGIServer((server_host, port), app, log=app.logger, **ssl_args)
            http_server.serve_forever()
        else:
            app.run(host=server_host, port=port, debug=input_args.debug, ssl_context=ssl_context)

    # On `start-multi-session` command, server creates one project per each browser sessions
    elif input_args.command == 'start-multi-session':
        server_host = input_args.host or '0.0.0.0'
        port = input_args.port or 8080

        if input_args.use_gevent:
            app.debug = input_args.debug
            http_server = WSGIServer((server_host, port), app, log=app.logger)
            http_server.serve_forever()
        else:
            app.run(host=server_host, port=port, debug=input_args.debug)
