from .base import BaseStorage
import logging
import os
from label_studio.models import Task, Completion, OldCompletion, UserScore, TrainingTask, StageRobin
from label_studio import db
from label_studio.utils.io import json_load
from sqlalchemy import func
import json

logger = logging.getLogger(__name__)


def checkAndgetTrainginTask(userID, batchid):
    q = db.session.query(Task.id).filter(Task.batch_id == batchid, Task.format_type == 1).subquery()
    # Task1 = db.session.query(Completion.task_id).filter(Completion.user_id == userID, Completion.task_id.in_(
    #     q))  # .delete(synchronize_session='fetch')
    # q1 = db.session.query(Task.id).filter(Task.batch_id == batchid, Task.format_type == 1).all()
    # for i in q1:
    #     print(i)
    # Taskidcompleted = db.session.query(Completion.task_id).filter(Completion.user_id == userID, Completion.task_id.in_(
    #     q)).subquery()  # .delete(synchronize_session='fetch')
    Taskcount = db.session.query(func.count(Completion.id)).filter(Completion.user_id == userID, Completion.task_id.in_(
        q)).scalar()  # .delete(synchronize_session='fetch')

    if Taskcount >= 2:
        print("Here 3", Taskcount)
        w = db.session.query(Completion).filter(Completion.user_id == userID,
                                                Completion.task_id.in_(q)).all()  # .delete(synchronize_session='fetch')
        for r in w:
            oldc = OldCompletion(user_id=r.user_id, task_id=r.task_id, data=r.data, completed_at=r.completed_at)
            db.session.add(oldc)
            db.session.delete(r)
        db.session.commit()
    # nextTask = db.session.query(Task).filter(Task.batch_id==batchid, Task.format_type == 1, Task.id.notin_(Taskidcompleted)).first()
        nextTask = db.session.execute(
            'SELECT * FROM TrainingTask WHERE batch_id=:batchid and TrainingTask.format_type == 1 and '
            'id not in (select task_id from completions where user_id = :userID and '
            'task_id in (select id from TrainingTask where batch_id= :batchid and TrainingTask.format_type == 1) ) order by id',
            {'userID': userID,'batchid':batchid }).first()
    # nextTask = db.session.execute(
    #     'SELECT * FROM TrainingTask WHERE batch_id=:batchid and format_type == 1 ',
    #     {'userID': userID, 'batchid': batchid}).first()

    return nextTask


def savestage(id, userID, currentRobinIndex, taskArray):
    try:
        if id == -1:
            dbrobinstage = StageRobin(user_id= userID, current_robin_index=currentRobinIndex, task_array=taskArray)
            db.session.add(dbrobinstage)
            db.session.commit()
        else:
            update_statement = 'UPDATE stage_robin SET current_robin_index = {0} WHERE id= {1}'.format(currentRobinIndex,id)
            db.session.execute(update_statement)
            db.session.commit()
    except Exception as e:
        logger.debug("Storage db Error ")
        logger.debug(e)


class JsonDBStorage(BaseStorage):

    description = 'JSON task file'
    def __init__(self, **kwargs):
        super(JsonDBStorage, self).__init__(**kwargs)
        if not self.importFromFile:
            logger.debug("returning flag set")
            return
        logger.debug("reading from File")
        Alltasks = {}
        if os.path.exists(self.path):
            Alltasks = json_load(self.path, int_keys=True)
        # logger.debug(Alltasks)
        # logger.debug(type(Alltasks))
        if len(Alltasks) != 0:
            for i, task in Alltasks.items():
                try:
                    # existing_task = Task.query.filter_by(username=username).first()
                    # if existing_task is None:
                    # logger.debug(SubTask)

                    # for task in SubTask:
                    # task = Alltasks[SubTask]
                    # logger.debug(type(task))
                    # logger.debug(task["data"])

                    dbtask = Task(text= task["data"]["text"], layout=task["data"]["layout"], groundTruth=task["data"]["groundTruth"])
                    db.session.add(dbtask)
                    db.session.commit()
                except Exception as e:
                    logger.debug("Storage db Error 3 ")
                    logger.debug(e)
        #     self.data = {}
        # elif isinstance(tasks, dict):
        #     self.data = tasks
        # elif isinstance(self.data, list):
        #     self.data = {int(task['id']): task for task in tasks}
        # self._save()

    # def _save(self):
    #     with open(self.path, mode='w', encoding='utf8') as fout:
            # json.dump(self.data, fout, ensure_ascii=False)


    @property
    def readable_path(self):
        return self.path

    def get(self, id):
        existing_task = Task.query.filter_by(id=id).first()
        if existing_task is not None:
            return existing_task
        return None
        # return self.data.get(int(id))

    def set(self, id, value):
        task = self.get(id)
        if task is not None:
            task.text = value["text"]
            task.layout = value["layout"]
            task.groundTruth = value["groundTruth"]
            # db.session.merge(task)
            db.session.commit()
        else:
            try:
                dbtask = Task(id=id,text=task["data"]["text"], layout=task["data"]["layout"],
                              groundTruth=task["data"]["groundTruth"])
                db.session.add(dbtask)
                db.session.commit()
            except Exception as e:
                logger.debug("Storage db Error ")
                logger.debug(e)
        # self.data[int(id)] = value
        # self._save()

    def __contains__(self, id):
        return self.get(id)
        # return id in self.data

    def set_many(self, ids, values):
        for id, value in zip(ids, values):
            self.set(id,value)
            # self.data[int(id)] = value
        # self._save()

    def ids(self):
        results = db.session.query(Task.id).all()
        return [value for value, in results]
        # return self.data.keys()

    def max_id(self):
        return db.session.query(db.func.max(Task.id)).scalar()
        # return max(self.ids(), default=-1)

    def items(self):
        return
        # return self.data.items()

    # def nextTask(self, userID, traingTask, batchid):
    def nextTask(self, userID, taskType, batchid):
        # db.session.query()
        print('next taks is called')
        nextTask = None

        if taskType in (1,2,3):
            nexttaskid = None
            try:
                robinstage = StageRobin.query.filter_by(user_id=userID).first()
                if robinstage == None:
                    randrobin = StageRobin.query.first()
                    if randrobin == None:
                        tasklist = db.session.execute(
                        'SELECT id FROM task WHERE id in (select task_id from completions where completions.user_id = 0 and completions.batch_id = :batchid ) and batch_id = :batchid and format_type = :taskType order by RANDOM() LIMIT 5', #random()
                        {'batchid': batchid, 'taskType': 1}).all()
                        taskArray = '-'.join([str(tid[0]) for tid in tasklist])
                    else:
                        taskArray = randrobin.task_array
                    nexttaskid = taskArray.split('-')[0]
                    savestage(-1, userID, 1, taskArray)
                else:
                    currentRobinIndex = robinstage.current_robin_index
                    taskArray = robinstage.task_array
                    id = robinstage.id
                    nexttaskid = taskArray.split('-')[currentRobinIndex]
                    currentRobinIndex = currentRobinIndex + 1
                    currentRobinIndex = currentRobinIndex % 5
                    savestage(id, userID, currentRobinIndex, taskArray)

                if nexttaskid is not None:
                    nextTask = db.session.execute(
                    'SELECT * FROM task WHERE id = :nexttaskid', 
                    {'nexttaskid': nexttaskid}).first()

            except Exception as e:
                print('Problem occured in getting task for first two stages. Here is the exception.')
                print(e)


        if taskType == 4:
            nextTask = db.session.execute(
                'SELECT * FROM task WHERE id in (select task_id from completions where completions.user_id = 0 and completions.batch_id = :batchid ) and id not in (select task_id from completions where user_id = :userID  and completions.batch_id = :batchid) and batch_id = :batchid and format_type = :taskType order by id LIMIT 1', #random()
                {'userID': userID, 'batchid': batchid, 'taskType': 1}).first()

        elif taskType == 5:
            #check first tasks which are not ever done by any users or admin
            query = 'SELECT * FROM task WHERE id not in (select task_id from completions where completions.batch_id = {0} ) and batch_id = {0} and format_type = {1} order by id LIMIT 1'.format(batchid,1)
            nextTask = db.session.execute(query).first()
            print(query)
            if nextTask is None:
                # check task which is not done by admin but only other users
                query = 'SELECT * FROM task WHERE id not in (select task_id from completions where completions.user_id = 0 and completions.batch_id = {0} ) and id not in (select task_id from completions where user_id = {1}  and completions.batch_id = {0}) and batch_id = {0} and format_type = {2} order by id LIMIT 1'.format(batchid,userID,1)
                nextTask = db.session.execute(query).first()
                print(query)
                if nextTask is None:
                    # check task which with admin completions
                    query = 'SELECT * FROM task WHERE id in (select task_id from completions where completions.user_id = 0 and completions.batch_id = {0} ) and id not in (select task_id from completions where user_id = {1}  and completions.batch_id = {0}) and batch_id = {0} and format_type = {2} order by id LIMIT 1'.format(batchid,userID,1)
                    nextTask = db.session.execute(query).first()
                    print(query)

        elif taskType == 6:
            query = 'SELECT * FROM task WHERE id not in (select task_id from completions where user_id = {0} and completions.batch_id = {1} ) and id in (select task_id from completions where completions.batch_id = {1} and completions.format_type = 5 and completions.accuracy_rank <= 80) and batch_id = {1} and format_type = 1 order by confidence_score ASC LIMIT 1'.format(userID,batchid)
            nextTask = db.session.execute(query).first()
            print(query)

        # TODO : Check if completion is empty the re elect task

        if nextTask is None:
            return None

        dictTask = dict(dict(nextTask).items())

        if taskType == 6:
            completion_data = db.session.execute(
                'select id,task_id,data,completed_at from completions where task_id = :id and format_type = 5 order by accuracy_rank ASC',
                {'id': nextTask.id}).first()
        else:
            completion_data = db.session.execute(
                'select id,task_id,data,completed_at from completions where task_id = :id',
                {'id': nextTask.id}).first()            

        if completion_data is not None:
            completionData = json.loads(completion_data.data)
            completionData['id'] = completion_data.id
            # logger.debug(json.dumps(completionData, indent=2))
            dictTask["completions"] = [completionData]  # [json.loads(completion.data)]
            dictTask['completed_at'] = completion_data.completed_at

        return dictTask

    def remove(self, key):
        task = self.get(int(key))
        if task is not None:
            db.session.delete(task)
        # self.data.pop(int(key), None)
        # self._save()

    def remove_all(self):
        return
        # self.data = {}
        # self._save()

    def empty(self):
        return False
        # return len(self.data) == 0

    def sync(self):
        pass

