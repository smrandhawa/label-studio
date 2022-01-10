
var result;
var didComplete;
var idtoLabelMap= {};
var ls;
function startIntroRE(_result, _ls) {
    $(".ant-spin-container").children().first().next().hide();
    result = _result;
    steps = 0;
    ls = _ls;
    q = introJs().setOptions({
        tooltipClass: 'customTooltip',doneLabel: "Next",scrollToElement: true, exitOnOverlayClick: false,exitOnEsc: false,showBullets: false,showStepNumbers: false,overlayOpacity: 0.5,disableInteraction: true,
        steps: [{
                title: 'Welcome',
                intro: 'Label Studio 👋'
            }]
    });
    q.oncomplete(function () {
        didComplete = true;
        // nextStepForTag(_result,0);
        idtoLabelMap[result[0].id] = result[0].value.text;
        idtoLabelMap[result[1].id] = result[1].value.text;
        nextStepForRelation(_result, 2);
    }).onexit(function (targetElement) {
        if (didComplete) {
            didComplete = false;
        }else {
            exitCall(ls);
        }
    }).onafterchange(function (el){
        afterChangeCall(q);
    });
    q.start();
}

/////////// Template for Next Step
function nextStepForTag(result, stepNumber) {
    idtoLabelMap[result[stepNumber].id] = result[stepNumber].value.text;
    setTimeout(function () {
        introJs().setOptions({doneLabel: "Next",scrollToElement: true, exitOnOverlayClick: false,exitOnEsc: false,showBullets: false,showStepNumbers: false,overlayOpacity: 0.5,disableInteraction: true,
            steps: [{
                title: 'Tag',
                element: $("span:contains('" + result[stepNumber].value.labels[0] + "')")[0],
                intro: 'Select Tag',
                position: 'top'
            }]
        }).oncomplete(function () {
            didComplete = true;
            setTimeout(function () {
                introJs().setOptions({doneLabel: "Next",scrollToElement: true, exitOnOverlayClick: false,exitOnEsc: false,showBullets: false,showStepNumbers: false,overlayOpacity: 0.5,disableInteraction: true,
                    steps: [{
                        title: 'Highlight Text!',
                        element: document.querySelector('[class^="Text_block"]'),
                        intro: 'Select Text with mouse!',
                        position: 'top'
                    }]
                }).oncomplete(function () {
                    didComplete = true;
                    setTimeout(function () {
                        if (document.getElementsByClassName('ls-entity-buttons')[0] != undefined) {
                            elem = document.getElementsByClassName('ls-entity-buttons')[0].children[2];
                            introJs().setOptions({
                                doneLabel: "Next",scrollToElement: true, exitOnOverlayClick: false,exitOnEsc: false,showBullets: false,showStepNumbers: false,overlayOpacity: 0.5,disableInteraction: true,
                                steps: [{
                                    title: 'Unselect',
                                    element: elem,
                                    intro: 'Unselect for next',
                                    position: 'top'
                                }]
                            }).oncomplete(function () {
                                didComplete = true;
                                FinishStep(stepNumber, ls);
                                setTimeout(function () {elem.click();}, (200));
                            }).onexit(function () {
                                if (didComplete) {
                                    didComplete = false;
                                } else {
                                    exitCall(ls);
                                }
                            }).onafterchange(function (el) {
                                afterChangeCall(q);
                            }).start();
                        } else {
                            FinishStep(stepNumber, ls);
                        }
                    }, (300));
                }).onexit(function () {
                    if (didComplete) {
                        didComplete = false;
                    } else {
                        //exitCall(ls);
                    }
                }).onafterchange(function (el) {
                    afterChangeCall(q);
                }).start();

                setTimeout(function () {
                    elemenq = document.querySelector('[class^="Text_line"]');
                    let range = new Range();
                    _text = result[stepNumber].value.text;
                    elem = elemenq.firstChild;
                    while(elem != null) {

                        if (elem.textContent.indexOf(_text) != -1) {
                            if (elem.firstChild != null) {
                               elem = elem1.firstChild;
                            }
                            break
                        } else {
                            elem = elem.nextSibling;
                        }
                    }
                    range.setStart(elem, elem.textContent.indexOf(_text));
                    range.setEnd(elem, elem.textContent.indexOf(_text) + _text.length);
                    window.getSelection().removeAllRanges();
                    window.getSelection().addRange(range);
                    var evt = document.createEvent("MouseEvents");
                    evt.initEvent("mouseup", true, true);
                    elemenq.dispatchEvent(evt);
                }, (500));
            }, (300));
        }).onexit(function () {
            if (didComplete) {
                didComplete = false;
            } else {

            }
        }).onafterchange(function (el) {
            afterChangeCall(q);
        }).start();
        setTimeout(function () {
            $("span:contains('" + result[stepNumber].value.labels[0] + "')")[0].click();
        }, (500));
    }, (300));
}

function nextStepForRelation(result, stepNumber) {
    dataLabel1 = idtoLabelMap[result[stepNumber].from_id]
    dataLabelElement1 = $( "span:contains('"+ dataLabel1 + "')")[1];
    dataLabel2 = idtoLabelMap[result[stepNumber].to_id];
    dataLabelElement2 = $( "span:contains('"+ dataLabel2 + "')")[1];
    setTimeout(function () {
        introJs().setOptions({
            doneLabel: "Next",scrollToElement: true, exitOnOverlayClick: false,exitOnEsc: false,showBullets: false,showStepNumbers: false,overlayOpacity: 0.5,disableInteraction: true,
            steps: [{
                title: 'Tag Selection for relation',
                element: dataLabelElement1,
                intro: 'Click 1st Tag',
                position: 'top'
            }]
        }).oncomplete(function () {
            didComplete = true;
            setTimeout(function () {
                labelbtns = document.getElementsByClassName('ls-entity-buttons')[0].children[0];
                introJs().setOptions({
                    doneLabel: "Next",scrollToElement: true, exitOnOverlayClick: false,exitOnEsc: false,showBullets: false,showStepNumbers: false,overlayOpacity: 0.5,disableInteraction: true,
                    steps: [{
                        title: 'Relations',
                        element: labelbtns,
                        intro: 'Click to start relation process',
                        position: 'top'
                    }]
                }).oncomplete(function () {
                    didComplete = true;
                    labelbtns.click();
                    setTimeout(function () {
                        introJs().setOptions({
                            doneLabel: "Next",scrollToElement: true, exitOnOverlayClick: false,exitOnEsc: false,showBullets: false,showStepNumbers: false,overlayOpacity: 0.5,disableInteraction: true,
                            steps: [{
                                title: 'Tag Selection for relation',
                                element: dataLabelElement2,
                                intro: 'Select 2nd Tag',
                                position: 'top'
                            }]
                        }).oncomplete(function () {
                           didComplete = true;
                           setTimeout(function () {
                                smbtn = document.getElementsByClassName("ant-btn-sm")[2];
                                introJs().setOptions({
                                    doneLabel: "Next",scrollToElement: true, exitOnOverlayClick: false,exitOnEsc: false,showBullets: false,showStepNumbers: false,overlayOpacity: 0.5,disableInteraction: true,
                                    steps: [{
                                        title: 'Relation Direction!',
                                        element: smbtn,
                                        intro: 'Click to change relation direction!',
                                        position: 'top'
                                    }]
                                }).oncomplete(function () {
                                    didComplete = true;
                                    setTimeout(function () {
                                        smbtn = document.getElementsByClassName("ant-btn-sm")[3];
                                        introJs().setOptions({
                                            doneLabel: "Next",scrollToElement: true, exitOnOverlayClick: false,exitOnEsc: false,showBullets: false,showStepNumbers: false,overlayOpacity: 0.5,disableInteraction: true,
                                            steps: [{
                                                title: 'Relation Type',
                                                element: smbtn,
                                                intro: 'Click to select relation Type!',
                                                position: 'top'
                                            }]
                                        }).oncomplete(function () {
                                            didComplete = true;
                                            setTimeout(function () {
                                                smbtn = document.getElementsByClassName("ant-select-selection-placeholder")[0];
                                                introJs().setOptions({
                                                    doneLabel: "Next",scrollToElement: true, exitOnOverlayClick: false,exitOnEsc: false,showBullets: false,showStepNumbers: false,overlayOpacity: 0.5,disableInteraction: true,
                                                    steps: [{
                                                        title: 'Relation Type',
                                                        element: smbtn,
                                                        intro: 'Click to open type menu!',
                                                        position: 'top'
                                                    }]
                                                }).oncomplete(function () {
                                                    didComplete = true;
                                                    generateMouseoverEvent(smbtn);
                                                    setTimeout(function () {
                                                        dropDown = document.getElementsByClassName("ant-select-dropdown")[0];
                                                        generateMouseoverEvent(smbtn);
                                                        introJs().setOptions({
                                                            doneLabel: "Next",scrollToElement: true, exitOnOverlayClick: false,exitOnEsc: false,showBullets: false,showStepNumbers: false,overlayOpacity: 0.5,disableInteraction: true,
                                                            steps: [{
                                                                title: 'Relation Type!',
                                                                element: dropDown,
                                                                intro: 'Click on relation type!',
                                                                position: 'left'
                                                            }]
                                                        }).oncomplete(function () {
                                                            didComplete = true;
                                                            // rlspan = document.querySelector('[title^="'+result[stepNumber].labels[0]+'"]');
                                                            // if (rlspan == null) {
                                                            //     generateMouseoverEvent(smbtn);

                                                                // rlspan = document.querySelector('[title^="'+result[stepNumber].labels[0]+'"]');
                                                            // }
                                                            ls.completionStore.completions[0].relationStore.relations[0].relations.findRelation(result[stepNumber].labels[0]).setSelected(true);
                                                            generateOnlyMouseoverEvent(smbtn);
                                                            // FinishStep(stepNumber,ls);
                                                            setTimeout(function () {
                                                                introJs().setOptions({
                                                                    doneLabel: "Done",scrollToElement: true, exitOnOverlayClick: false,exitOnEsc: false,showBullets: false,showStepNumbers: false,overlayOpacity: 0.5,disableInteraction: true,
                                                                    steps: [{
                                                                        title: 'Finished',
                                                                        intro: 'Let see the final shape!',
                                                                        position: 'top'
                                                                    }]
                                                                }).oncomplete(function () {
                                                                    didComplete = true;
                                                                    // Next function call
                                                                }).onexit(function () {
                                                                    exitCall(ls);
                                                                }).start();
                                                            }, (600));
                                                        }).onexit(function () {
                                                            if (didComplete) {
                                                                didComplete = false;
                                                            } else {
                                                                exitCall(ls);
                                                            }
                                                        }).onafterchange(function (el) {
                                                            afterChangeCall(q);
                                                        }).start();
                                                        setTimeout(function () {
                                                            generateMouseoverEvent(smbtn);
                                                        }, (600));
                                                    }, (600));
                                                }).onexit(function () {
                                                    if (didComplete) {
                                                        didComplete = false;
                                                    } else {
                                                        exitCall(ls);
                                                    }
                                                }).onafterchange(function (el) {
                                                    afterChangeCall(q);
                                                }).start();
                                                // setTimeout(function () {
                                                //     generateClickEvent(smbtn);
                                                // }, (1000));
                                            }, (600));
                                        }).onexit(function () {
                                            if (didComplete) {
                                                didComplete = false;
                                            } else {
                                                exitCall(ls);
                                            }
                                        }).onafterchange(function (el) {
                                            afterChangeCall(q);
                                        }).start();
                                        setTimeout(function () {
                                            smbtn.click()
                                        }, (700));
                                    }, (600));

                                }).onexit(function () {
                                    if (didComplete) {
                                        didComplete = false;
                                    } else {
                                        exitCall(ls);
                                    }
                                }).onafterchange(function (el) {
                                    afterChangeCall(q);
                                }).start();
                            }, (600));
                        }).onexit(function () {
                            if (didComplete) {
                                didComplete = false;
                            } else {
                                exitCall(ls);
                            }
                        }).onafterchange(function (el) {
                            afterChangeCall(q);
                        }).start();
                        setTimeout(function () {
                            generateClickEvent(dataLabelElement2);
                        }, (1000));
                    }, (600));
                }).onexit(function () {
                    if (didComplete) {
                        didComplete = false;
                    } else {
                        exitCall(ls);
                    }
                }).onafterchange(function (el) {
                    afterChangeCall(q);
                }).start();
            }, (600));
        }).onexit(function () {
            if (didComplete) {
                didComplete = false;
            } else {
                exitCall(ls);
            }
        }).onafterchange(function (el) {
            afterChangeCall(q);
        }).start();
        setTimeout(function () {
            generateClickEvent(dataLabelElement1);
        }, (1000));
    }, (600));
}

function FinishStep(stepNumber, ls){
    stepNumber++;
    if (stepNumber < result.length) {
        if (result[stepNumber].type === "labels") {
            nextStepForTag(result, stepNumber);
        } else if (result[stepNumber].type === "relation") {
            nextStepForRelation(result, stepNumber);
        }
     }
    else {
        //exitCall(ls);
    }
}


function generateClickEvent(element){
    var evt = document.createEvent("MouseEvents");
    evt.initEvent("mouseover", true, true);
    element.dispatchEvent(evt);
    var evt = document.createEvent("MouseEvents");
    evt.initEvent("mousedown", true, true);
    element.dispatchEvent(evt);
    var evt = document.createEvent("MouseEvents");
    evt.initEvent("click", true, false);
    element.dispatchEvent(evt);
}

function generateMouseoverEvent(element){
    var evt = document.createEvent("MouseEvents");
    evt.initEvent("mouseout", true, true);
    element.dispatchEvent(evt);
    var evt = document.createEvent("MouseEvents");
    evt.initEvent("mouseover", true, true);
    element.dispatchEvent(evt);
    var evt = document.createEvent("MouseEvents");
    evt.initEvent("mousedown", true, true);
    element.dispatchEvent(evt);
    var evt = document.createEvent("MouseEvents");
    evt.initEvent("mouseup", true, true);
    element.dispatchEvent(evt);
    var evt = document.createEvent("MouseEvents");
    evt.initEvent("click", true, false);
    element.dispatchEvent(evt);
}

function generateOnlyMouseoverEvent(element){
    var evt = document.createEvent("MouseEvents");
    evt.initEvent("mouseout", true, true);
    element.dispatchEvent(evt);
}

function afterChangeCall(q){
    $(".introjs-tooltipbuttons").prepend("<a role=\"button\" tabindex=\"0\" class=\"introjs-button introjs-prevbutton myexit \">Skip all</a>");
    $(".myexit").on('click',function () {
       q.exit(true);
    });
    $(".introjs-skipbutton").hide();
}

function waitCall(){
    $(".myexit").attr("disabled", true);
    $(".introjs-nextbutton").attr("disabled", true);
}

function resumeCall(){
    $(".myexit").attr("disabled", false);
    $(".introjs-nextbutton").attr("disabled", false);
}

function exitCall(ls){
    let cs = ls.completionStore;
    let c = {id: ls.completionStore.completions[1].id, editable: false};
    if (c.id) cs.selectCompletion(c.id);
    if (TaskdataObj.layout_id == 2 && TaskdataObj.batch_id == 5) {
        $($("span:contains('" + result[0].value.labels[0] + "')")[0].parentElement).children().hide();
        // $($("span:contains('" + result[0].value.labels[0] + "')")[0].parentElement).find("*").off("click");
        generateOnlyMouseoverEvent(document.getElementsByClassName("Relations_item__2qMzb")[0]);
    }

    var Skipbtn = $('.ls-skip-btn').children().first();
    Skipbtn.html('').append("<span>Show me more</span>");
    $('.ls-update-btn').hide();
    $('.ls-submit-btn').hide();
    Skipbtn.on('click', function () {
        c = ls.completionStore.addCompletion({userGenerate: true});
        cs.selectCompletion(c.id);
        // $($(".Controls_container__LTeAA").children).remove();
        $(".Controls_container__LTeAA").find("*").attr("disabled", true)
    });

    btndiv = $(".Controls_container__LTeAA")[0];
    var btn = $('<button type="button" class="ant-btn ant-btn-primary helpBtn1"><span>Next</span></button>');
    btndiv.append(btn[0]);
    $('.helpBtn1').on('click', function () {
      c = ls.completionStore.addCompletion({userGenerate: true});
      ls.completionStore.selectCompletion(c.id);
      ls.submitCompletion();
      // $(".Controls_container__LTeAA").hide();
        $(".Controls_container__LTeAA").find("*").attr("disabled", true)
    });

}

function handleButtons(ls){
    let cs = ls.completionStore;
    let c = {id: ls.completionStore.completions[1].id, editable: false};

    var Skipbtn = $('.ls-skip-btn').children().first();
    Skipbtn.html('').append("<span>Show me more</span>");;
    $('.ls-update-btn').hide();
    $('.ls-submit-btn').hide();
    Skipbtn.on('click', function () {
        c = ls.completionStore.addCompletion({userGenerate: true});
        cs.selectCompletion(c.id);
        // $($(".Controls_container__LTeAA").children).remove();
        $(".Controls_container__LTeAA").find("*").attr("disabled", true)
    });

    btndiv = $(".Controls_container__LTeAA")[0];
    var btn = $('<button type="button" class="ant-btn ant-btn-primary helpBtn1"><span>Next</span></button>');
    btndiv.append(btn[0]);
    $('.helpBtn1').on('click', function () {
      c = ls.completionStore.addCompletion({userGenerate: true});
      ls.completionStore.selectCompletion(c.id);
      ls.submitCompletion();
      // $(".Controls_container__LTeAA").hide();
        $(".Controls_container__LTeAA").find("*").attr("disabled", true)
    });

}

function nextStep(result, stepNumber) {

    setTimeout(function () {
        introJs().setOptions({
            doneLabel: "Next",scrollToElement: true, exitOnOverlayClick: false,exitOnEsc: false,showBullets: false,showStepNumbers: false,overlayOpacity: 0.5,disableInteraction: true,
            steps: [{
                title: 'Tag',
                element: $("span:contains('" + result[stepNumber].value.labels[0] + "')")[0],
                intro: 'Select 1st Tag',
                position: 'top'
            }]
        }).oncomplete(function () {
            didComplete = true;
            // Next function call
        }).onexit(function () {
            if (didComplete) {
                didComplete = false;
            } else {
                exitCall(ls);
            }
        }).onafterchange(function (el) {
            afterChangeCall(q);
        }).start();
        setTimeout(function () {
            // LAter Function // click etc
        }, (1000));
    }, (600));
}

function startIntroPolygon(_result, _ls) {
    $(".ant-spin-container").children().first().next().hide();
    result = _result;
    steps = 0;
    ls = _ls;
    q = introJs().setOptions({
        tooltipClass: 'customTooltip',doneLabel: "Next",scrollToElement: true, exitOnOverlayClick: false,exitOnEsc: false,showBullets: false,showStepNumbers: false,overlayOpacity: 0.5,disableInteraction: true,
        steps: [{
                title: 'Welcome',
                intro: 'Label Studio 👋 <br>  Here you will see how to draw a polygon'
            }]
    });
    q.oncomplete(function () {
        didComplete = true;

        setTimeout(function () {
            introJs().setOptions({
                doneLabel: "Next",scrollToElement: true, exitOnOverlayClick: false,exitOnEsc: false,showBullets: false,showStepNumbers: false,overlayOpacity: 0.5,disableInteraction: true,
                steps: [{
                    title: 'Tag',
                    element: $("span:contains('" + result[0].value.polygonlabels[0] + "')")[0],
                    intro: 'Select Tag',
                    position: 'top'
                }]
            }).oncomplete(function () {
                didComplete = true;
                CreatePath(result, 0);
            }).onexit(function () {
                if (didComplete) {
                    didComplete = false;
                } else {
                    exitCall(ls);
                }
            }).onafterchange(function (el) {
                afterChangeCall(q);
            }).start();
            setTimeout(function () {
                $("span:contains('" + result[0].value.polygonlabels[0] + "')")[0].click();
            }, (1000));
        }, (600));

    }).onexit(function (targetElement) {
        if (didComplete) {
            didComplete = false;
        }else {
            exitCall(ls);
        }
    }).onafterchange(function (el){
        afterChangeCall(q);
    });
    q.start();
}

function CreatePath(result, stepNumber){
    setTimeout(function () {
        introJs().setOptions({
            doneLabel: "Next",scrollToElement: true, exitOnOverlayClick: false,exitOnEsc: false,showBullets: false,showStepNumbers: false,overlayOpacity: 0.5,disableInteraction: true,
            steps: [{
                title: 'Draw boundary',
                element: $("canvas")[0],
                intro: 'Click on image to start drawing',
                position: 'top'
            }]
        }).oncomplete(function () {
            didComplete = true;
            FinishStep(stepNumber, ls);
        }).onexit(function () {
            if (didComplete) {
                didComplete = false;
            } else {
                exitCall(ls);
            }
        }).onafterchange(function (el) {
            afterChangeCall(q);
        }).start();
        setTimeout(function () {
            waitCall();
            myTime = setInterval(function () {
                if (stepNumber == result[0].value.points.length ){
                    const lastPoint = Konva.stages[0].find("Circle").slice(-1)[0];
                    const firstPoint = lastPoint.parent.find("Circle")[0];
                    firstPoint.fire("mouseover");
                    firstPoint.fire("click");
                    clearTimeout(myTime);
                    resumeCall();
                } else {
                    let x = result[0].value.points[stepNumber][0] * ($("canvas")[0].clientWidth / 100);
                    let y = result[0].value.points[stepNumber][1] * ($("canvas")[0].clientHeight / 100);
                    Konva.stages[0].fire("click", {clientX: x, clientY: y, evt: {offsetX: x, offsetY: y}});
                }
                stepNumber++;
                // if (stepNumber > result[0].value.points.length || stepNumber%5 == 0){
                //     clearTimeout(myTime);
                //     resumeCall();
                // }
            }, (400));
        }, (500));
    }, (600));
}
function doNextPoints(result, stepNumber){
    waitCall();
    myTime = setInterval(function () {
        waitCall();
        if (stepNumber == result[0].value.points.length ){
            const lastPoint = Konva.stages[0].find("Circle").slice(-1)[0];
            const firstPoint = lastPoint.parent.find("Circle")[0];
            firstPoint.fire("mouseover");
            firstPoint.fire("click");
            // resumeCall();
        } else {
            let x = result[0].value.points[stepNumber][0] * ($("canvas")[0].clientWidth / 100);
            let y = result[0].value.points[stepNumber][1] * ($("canvas")[0].clientHeight / 100);
            Konva.stages[0].fire("click", {clientX: x, clientY: y, evt: {offsetX: x, offsetY: y}});
        }
        stepNumber++;
        if (stepNumber > result[0].value.points.length || stepNumber%5 == 0){
            clearTimeout(myTime);
            resumeCall();
        }
    }, (400));
}


function startIntroNE(_result, _ls) {
    $(".ant-spin-container").children().first().next().hide();
    result = _result;
    steps = 0;
    ls = _ls;
    handleButtons(ls);
    q = introJs().setOptions({
        tooltipClass: 'customTooltip',doneLabel: "Next",scrollToElement: true, exitOnOverlayClick: false,exitOnEsc: false,showBullets: false,showStepNumbers: false,overlayOpacity: 0.5,disableInteraction: true,
        steps: [{
                title: 'Welcome',
                intro: 'Label Studio 👋'
            }]
    });
    q.oncomplete(function () {
        didComplete = true;
        nextStepForTag(_result,0);
    }).onexit(function (targetElement) {
        if (didComplete) {
            didComplete = false;
        }else {
            //exitCall(ls);
        }
    }).onafterchange(function (el){
        afterChangeCall(q);
    });
    q.start();
}


function startIntroImgCls(_result, _ls) {
    $(".ant-spin-container").children().first().next().hide();
    result = _result;
    steps = 0;
    ls = _ls;

    q = introJs().setOptions({
        tooltipClass: 'customTooltip',doneLabel: "Next",scrollToElement: true, exitOnOverlayClick: false,exitOnEsc: false,showBullets: false,showStepNumbers: false,overlayOpacity: 0.5,disableInteraction: true,
        steps: [{
                title: 'Welcome',
                intro: 'Label Studio 👋 <br> Here you will see how to do classification'
            }]
    });
    q.oncomplete(function () {
        didComplete = true;

        setTimeout(function () {
            introJs().setOptions({
                doneLabel: "Next",scrollToElement: true, exitOnOverlayClick: false,exitOnEsc: false,showBullets: false,showStepNumbers: false,overlayOpacity: 0.5,disableInteraction: true,
                steps: [{
                    title: 'Classification',
                    element: $(".ant-form")[0],
                    intro: 'Select muliple class labes',
                    position: 'top'
                }]
            }).oncomplete(function () {
                didComplete = true;
            }).onexit(function () {
                exitCall(ls);
            }).onafterchange(function (el) {
                afterChangeCall(q);
            }).start();
            setTimeout(function () {
                waitCall();
                stepNumber = 0;
                myTime = setInterval(function () {
                    if (stepNumber == result[0].value.choices.length ){
                        clearTimeout(myTime);
                        resumeCall();
                    } else {
                        $("span:contains('" + result[0].value.choices[stepNumber] + "')").parent()[0].click()
                        stepNumber++;
                    }
                }, (500));
                //                $("span:contains('" + result[0].value.choices[0] + "')").parent()[0].click();
            }, (1000));
        }, (600));

    }).onexit(function (targetElement) {
        if (didComplete) {
            didComplete = false;
        }else {
            exitCall(ls);
        }
    }).onafterchange(function (el){
        afterChangeCall(q);
    });
    q.start();
}


function startIntroRectangle(_result, _ls) {
    $(".ant-spin-container").children().first().next().hide();
    console.log('startIntroRectangleResult:', _result);
    result = _result;
    steps = 0;
    ls = _ls;
    q = introJs().setOptions({
        tooltipClass: 'customTooltip',doneLabel: "Next",scrollToElement: true, exitOnOverlayClick: false,exitOnEsc: false,showBullets: false,showStepNumbers: false,overlayOpacity: 0.5,disableInteraction: true,
        steps: [{
                title: 'Welcome',
                intro: 'Label Studio 👋 <br>  Here you will see how to draw a polygon'
            }]
    });
    q.oncomplete(function () {
        didComplete = true;

        setTimeout(function () {
            introJs().setOptions({
                doneLabel: "Next",scrollToElement: true, exitOnOverlayClick: false,exitOnEsc: false,showBullets: false,showStepNumbers: false,overlayOpacity: 0.5,disableInteraction: true,
                steps: [{
                    title: 'Tag',
                    element: $("span:contains('" + result[0].value.rectanglelabels[0] + "')")[0],
                    intro: 'Select Tag',
                    position: 'top'
                }]
            }).oncomplete(function () {
                didComplete = true;
                CreatePath(result, 0);
            }).onexit(function () {
                if (didComplete) {
                    didComplete = false;
                } else {
                    exitCall(ls);
                }
            }).onafterchange(function (el) {
                afterChangeCall(q);
            }).start();
            setTimeout(function () {
                $("span:contains('" + result[0].value.rectanglelabels[0] + "')")[0].click();
            }, (1000));
        }, (600));

    }).onexit(function (targetElement) {
        if (didComplete) {
            didComplete = false;
        }else {
            exitCall(ls);
        }
    }).onafterchange(function (el){
        afterChangeCall(q);
    });
    q.start();
}
