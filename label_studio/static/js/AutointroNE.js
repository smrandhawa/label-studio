
var result;
var didComplete;
var idtoLabelMap= {};
var ls;
function startIntro(_result, _ls) {
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
        nextStepForTag(_result,0);
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
                intro: 'Select 1st Tag',
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
                    elemenq = document.querySelector('[class^="Text_line"]');
                    let range = new Range();
                    _text = result[stepNumber].value.text;
                    elem = elemenq.firstChild;
                    while(elem != null) {
                        if (elem.textContent.indexOf(_text) != -1) {
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
                }, (1000));
            }, (600));
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
        }, (1000));
    }, (600));
}

function nextStepForRelation(result, stepNumber) {
    dataLabel1 = idtoLabelMap[result[stepNumber].from_id]
    dataLabelElement1 = $( "span:contains('"+ dataLabel1 + "')")[1]
    dataLabel2 = idtoLabelMap[result[stepNumber].to_id];
    dataLabelElement2 = $( "span:contains('"+ dataLabel2 + "')")[1]
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
        exitCall(ls);
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

function exitCall(ls){
    let cs = ls.completionStore;
    let c = {id: ls.completionStore.completions[1].id, editable: false};
    if (c.id) cs.selectCompletion(c.id);
    var Skipbtn = $('.ls-skip-btn').children().first();
    Skipbtn.html('').append("<span>Show me more</span>");
    $('.ls-update-btn').hide();
    $('.ls-submit-btn').hide();
    Skipbtn.on('click', function () {
        c = ls.completionStore.addCompletion({userGenerate: true});
        cs.selectCompletion(c.id);
        $(".Controls_container__LTeAA").hide();
    });

    btndiv = $(".Controls_container__LTeAA")[0];
    var btn = $('<button type="button" class="ant-btn ant-btn-primary helpBtn"><span>Next</span></button>');
    btndiv.append(btn[0]);
    $('.helpBtn').on('click', function () {
      c = ls.completionStore.addCompletion({userGenerate: true});
      ls.completionStore.selectCompletion(c.id);
      ls.submitCompletion();
      $(".Controls_container__LTeAA").hide();
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

//             $(".introjs-tooltipbuttons").prepend("<a role=\"button\" tabindex=\"0\" class=\"introjs-button introjs-prevbutton myexit \">Exit</a>");
//             $(".introjs-skipbutton").hide();
//             $(".myexit").on('click', function () {
//                 q.exit(true);
//             });

