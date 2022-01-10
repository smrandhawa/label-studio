from .base import BaseStorage
import logging
import os
from label_studio.models import Task
from label_studio import db
from label_studio.utils.io import json_load

logger = logging.getLogger(__name__)

class JsonDBStorage(BaseStorage):

    description = 'JSON task file'
    def __init__(self, **kwargs):
        super(JsonDBStorage, self).__init__(**kwargs)
        return
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

                    dbtask = Task(text= task["data"]["text"],layout=task["data"]["layout"],groundTruth=task["data"]["groundTruth"])
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
        return self.data.items()

    def nextTask(self, userID):
        # db.session.query()
        nextTask = db.session.execute('SELECT * FROM task WHERE id not in (select id from completions where user_id = :userID ) order by id', {'userID': userID}).first()
        logger.debug(nextTask)
        logger.debug(type(nextTask))
        # for r in nextTask:
            # print(r[0])  # Access by positional index
            # print(r['my_column'])  # Access by column name as a string
            # r_dict = dict(r.items())  # convert to dict keyed by column names
            #  return r.__dict_
        return dict(nextTask.items())

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

