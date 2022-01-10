from label_studio.utils.misc import DirectionSwitch, timestamp_to_local_datetime
from label_studio.utils.uri_resolver import resolve_task_data_uri
from label_studio.models import Completion, Layout
from label_studio import db
import flask_login
import json

class DataManagerException(Exception):
    pass


def count_total_users_tasks(params):
    count_total_tasks = db.session.execute(
        'select count(*) from completions where task_id in (SELECT id FROM task WHERE batch_id = :batchid) and user_id not in (select id from user where is_admin = 1)',
        {'batchid': params.batchid}).scalar()
    return count_total_tasks


def prepare_tasks(project, params):
    order, page, page_size = params.order, params.page, params.page_size
    fields = params.fields

    # print(page)
    # print(page_size)


    ascending = order[0] == '-'
    order = order[1:] if order[0] == '-' else order
    if order not in ['id', 'completed_at', 'has_cancelled_completions']:
        raise DataManagerException('Incorrect order')

    # get task ids and sort them by completed time
    # task_ids = project.source_storage.ids()
    # completed_at = project.get_completed_at()  # task can have multiple completions, get the last of completed
    # cancelled_status = project.get_cancelled_status()
    #task_ids = project.source_storage.ids()

    # completed_at_data = db.session.query(Completion.task_id,Completion.data,Completion.completed_at).filter_by(user_id=flask_login.current_user.get_id()).all()
    completed_at_data = db.session.execute(
        'select task_id,data,completed_at from completions where task_id in (SELECT id FROM task WHERE batch_id = :batchid) and user_id not in (select id from user where is_admin = 1)',
        {'batchid': params.batchid})

    completed_at = {}
    cancelled_status = {}
    pre_order = []
    # for id, data, time in completed_at_data:
    #     if time is not None:
    #         completed_at[id] = timestamp_to_local_datetime(time).strftime('%Y-%m-%d %H:%M:%S')
    #     data = json.loads(data)
    #     if "skipped" in data :
    #         cancelled_status[id] = data["skipped"]
    #     if "was_cancelled" in data:
    #         cancelled_status[id] = data["was_cancelled"]
    #
    for id, data, time in completed_at_data:
        item = {}
        item['id'] = id
        if time is not None:
            item['completed_at'] = timestamp_to_local_datetime(time).strftime('%Y-%m-%d %H:%M:%S')
        else:
            item['completed_at'] = None

        data = json.loads(data)
        if "skipped" in data:
            item['has_cancelled_completions'] = data["skipped"]
        else:
            item['has_cancelled_completions'] = None
        if "was_cancelled" in data:
            item['has_cancelled_completions'] = data["was_cancelled"]
        else:
            item['has_cancelled_completions'] = None
        pre_order.append(item)

    # ordering
    # pre_order = ({
    #     'id': i,
    #     'completed_at': completed_at[i] if i in completed_at else None,
    #     'has_cancelled_completions': cancelled_status[i] if i in cancelled_status else None,
    # } for i in task_ids)

    if order == 'id':
        ordered = sorted(pre_order, key=lambda x: x['id'], reverse=ascending)

    else:
        # for has_cancelled_completions use two keys ordering
        if order == 'has_cancelled_completions':
            ordered = sorted(pre_order,
                             key=lambda x: (DirectionSwitch(x['has_cancelled_completions'], not ascending),
                                            DirectionSwitch(x['completed_at'], False)))
        # another orderings
        else:
            ordered = sorted(pre_order, key=lambda x: (DirectionSwitch(x[order], not ascending)))

    paginated = ordered[(page - 1) * page_size:page * page_size]

    # print(paginated)
    # get tasks with completions
    tasks = []

    for item in paginated:
        i = item['id']
        task = project.source_storage.get(i) #project.get_task_with_completions(i)
        completion = Completion.query.filter_by(user_id=flask_login.current_user.get_id(),task_id=i).first()
        db_layout = Layout.query.filter_by(id=task.layout_id).first()
        task = task.__dict__
        task.pop('_sa_instance_state', None)
        if completion is not None:
            completionData = json.loads(completion.data)
            completionData['id'] = completion.id
            # logger.debug(json.dumps(completionData, indent=2))
            task["completion"] = [completionData]#[json.loads(completion.data)]
            task['completed_at'] = item['completed_at']
            task['has_cancelled_completions'] = item['has_cancelled_completions']
        task['data'] = {}
        task['data']['text'] = task['text']
        task.pop('text', None)
        task["layout"] = db_layout.data
        task['data'].pop('predictions', None)
        

        # don't resolve data (s3/gcs is slow) if it's not in fields
        if 'all' in fields or 'data' in fields:
            task = resolve_task_data_uri(task, project=project)

        # leave only chosen fields
        if 'all' not in fields:
            task = {field: task[field] for field in fields}

        tasks.append(task)

    return tasks
