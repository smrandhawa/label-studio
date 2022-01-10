
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
                FinishStep(ls);
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

function FinishStep(ls){
    exitCall(ls);
}

function afterChangeCall(q){
    $(".introjs-tooltipbuttons").prepend("<a role=\"button\" tabindex=\"0\" class=\"introjs-button introjs-prevbutton myexit \">Skip all</a>");
    $(".myexit").on('click',function () {
       q.exit(true);
    });
    $(".introjs-skipbutton").hide();
    $(".introjs-nextbutton").attr("tabindex", 1);
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
            waitCall();
            myTime = setInterval(function () {
                $("span:contains('" + result[stepNumber].value.choices[stepNumber] + "')")[0].click();
                if (stepNumber == result[0].value.choices.length ){
                    clearTimeout(myTime);
                    resumeCall();
                }
                stepNumber++;
            }, (400));
        }, (1000));
    }, (600));
}

function waitCall(){
    $(".myexit").attr("disabled", true);
    $(".introjs-nextbutton").attr("disabled", true);
}

function resumeCall(){
    $(".myexit").attr("disabled", false);
    $(".introjs-nextbutton").attr("disabled", false);
}
