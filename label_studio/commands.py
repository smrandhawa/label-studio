

@app.cli.command("loadtasksold")
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

@app.cli.command("loadtasks")
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

@app.cli.command("loadlayout")
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
