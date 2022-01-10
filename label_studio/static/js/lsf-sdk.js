/*
 * Label Studio Frontend SDK - inter-layer code that connects LSB server
 * implementation with the Frontend part. At the moment it's based on
 * callbacks.
 */

const API_URL = {
  MAIN: "api",
  PROJECT: "/project",
  TASKS: "/tasks",
  COMPLETIONS: "/completions",
  CANCEL: "?was_cancelled=1",
  NEXT: "/next",
    TraingTask: "traingTask=",
  INSTRUCTION: "/project?fields=instruction"
};

var lastId;
var tmpLS;
var isAdmin;
var workerId;
var TaskdataObj;
var urlParam;
var hitId, turkSubmitTo, assignmentId, gameid;

const Requests = (function(window) {
  const handleResponse = res => {
    if (res.status !== 200 || res.status !== 201) {
      return res;
    } else {
      return res.json();
    }
  };

  const wrapperRequest = (url, method, headers, body) => {
    return window
      .fetch(url, {
        method: method,
        headers: headers,
        credentials: "include",
        body: body,
      })
      .then(response => handleResponse(response));
  };

  const fetcher = url => {
    return wrapperRequest(url, "GET", { Accept: "application/json" });
  };

  const fetcherAuth = async (url, data) => {
    const response = await window.fetch(url, {
      method: "GET",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        Authorization: "Basic " + btoa(data.username + ":" + data.password),
      },
      credentials: "same-origin",
    });
    return handleResponse(response);
  };

  const poster = (url, body) => {
    return wrapperRequest(url, "POST", { Accept: "application/json", "Content-Type": "application/json" }, body);
  };

  const patch = (url, body) => {
    return wrapperRequest(
      url,
      "PATCH",
      {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body,
    );
  };

  const remover = (url, body) => {
    return wrapperRequest(
      url,
      "DELETE",
      {
        "Content-Type": "application/json",
      },
      body,
    );
  };

  return {
    fetcher: fetcher,
    poster: poster,
    patch: patch,
    remover: remover,
  };
})(window);

const _loadTask = function(ls, url, completionID, reset) {
    try {
        const req = Requests.fetcher(url);

        req.then(function(loadedTask) {
            if (loadedTask instanceof Response && loadedTask.status === 404) {
                ls.setFlags({ isLoading: false, noTask: true });
                return;
            }

            if (loadedTask instanceof Response && loadedTask.status === 403) {
                ls.setFlags({ isLoading: false, noAccess: true });
                return;
            }

            loadedTask.json().then(response => {
                /**
                 * Convert received data to string for MST support
                 */
                // ls = LSF_SDK("label-studio", response.label_config_line, null);
                // ls.LS.config(response.label_config_line)
                // if (reset == true) {
                //     response.completionID = completionID
                //     ls.resetState();
                //     delete window.LSF_SDK;
                //     window.LSF_SDK = LSF_SDK("label-studio", response.layout, null, false, response.data.description, true, response, response.data.batch_id, 1);
                //     // ls = window.LSF_SDK;
                //    MyDOList(window.LSF_SDK, window.LSF_SDK.task);
                // }
                // else {
                    /**
                     * Add new data from received task
                     */
                // console.log(response);;
                response.data = JSON.stringify(response.data);
                TempTaskData = response;
                tmpLS = ls;
                ls.resetState();
                ls.assignTask(response);
                ls.initializeStore(_convertTask(response));
                ls.updateDescription(response.description);

                let cs = ls.completionStore;
                let c;

                if (ls.completionStore.completions.length > 0 && (completionID === 'auto')) {
                //if (ls.completionStore.completions.length > 0 && (completionID === 'auto' || isAdmin)) {
                  c = {id: ls.completionStore.completions[0].id};
                }

                else if (cs.predictions.length > 0) {
                    c = ls.completionStore.addCompletionFromPrediction(cs.predictions[0]);
                }

                // we are on history item, take completion id from history
                else if (ls.completionStore.completions.length > 0 && completionID) {
                    c = {id: 1};
                }

                else if (ls.completionStore.completions.length > 0 && (response.format_type == 1 || response.format_type == 6) ) {
                    c = {id: completionID};
                }

                else {
                    c = ls.completionStore.addCompletion({ userGenerate: true });
                }

                if (c.id) cs.selectCompletion(c.id);

                // fix for broken old references in mst
                cs.selected.setupHotKeys();
                // ls.onTaskLoad(ls, ls.task);
                setTimeout(function () {
                      MyDOList(ls, ls.task);
                      if (response.format_type >= 3 && response.format_type < 6){
                      btndiv = $(".Controls_container__LTeAA")[0];
                        $('.ls-update-btn').hide();
                        $('.ls-submit-btn').hide();

                        var submitbutton = $('<button type="button" class="ant-btn ant-btn-primary mysubmitbtn"><span role="img" aria-label="check" class="anticon anticon-check"><svg viewBox="64 64 896 896" focusable="false" class="" data-icon="check" width="1em" height="1em" fill="currentColor" aria-hidden="true"><path d="M912 190h-69.9c-9.8 0-19.1 4.5-25.1 12.2L404.7 724.5 207 474a32 32 0 00-25.1-12.2H112c-6.7 0-10.4 7.7-6.3 12.9l273.9 347c12.8 16.2 37.4 16.2 50.3 0l488.4-618.9c4.1-5.1.4-12.8-6.3-12.8z"></path></svg></span><span>Submit </span></button>');
                        btndiv.append(submitbutton[0]);
                        submitbutton.on('click', function(){
                            if (c.serializeCompletion().length == 0){
                              if (ls.task.dataObj.layout_id == 2){
                                if (response.format_type == 3)
                                {
                                  alert("Response can not be empty! Check the instructions and see answer to add at least one annotation.");
                                }
                                else
                                {
                                  alert("Response can not be empty! Check the instructions to add at least one annotation.");
                                }
                                
                              }
                              else{
                                if (response.format_type == 3)
                                {
                                  alert("Response can not be empty! Check the instructions and see answer to add a similar reponse.");
                                }
                                else
                                {
                                  alert("Response can not be empty! Check the instructions and add some response.");
                                }
                              }
                            }else
                            {ls.submitCompletion();}
                          });
                      }
                      
                }, (100));
                ls.setFlags({ isLoading: false });
              // }
            })
        });
    } catch (err) {
        console.error("Failed to load next task ", err);
    }
};

function MyDOList(ls, task){
    // if(task.dataObj.layout_id == 2) {
    //     $('.Text_line__2JZG0').css("word-spacing", "50px");
    // }
    TaskdataObj = task.dataObj;
    if((task.dataObj.layout_id == 8 || task.dataObj.layout_id == 5) && !ls.settings.showLabels) {
        ls.settings.toggleShowLabels();
    }

    if ( task.dataObj.layout_id == 2 && task.dataObj.batch_id == 5 ){
       if (task.dataObj.format_type != 1 && task.dataObj.format_type != 6) {
           result = task.dataObj.completions[0].result;
           $("span:contains('" + result[0].value.labels[0] + "')")[0].click();
           elemenq = document.querySelector('[class^="Text_line"]');
           let range = new Range();
           _text = result[0].value.text;
           elem = elemenq.firstChild;
           while (elem != null) {
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

           $("span:contains('" + result[1].value.labels[0] + "')")[0].click();
           elemenq = document.querySelector('[class^="Text_line"]');
           let range1 = new Range();
           _text = result[1].value.text;
           elem1 = elemenq.firstChild;
           while (elem1 != null) {
               if (elem1.textContent.indexOf(_text) != -1) {
                   if (elem1.firstChild != null) {
                       elem1 = elem1.firstChild;
                   }
                   break
               } else {
                   elem1 = elem1.nextSibling;
               }
           }
           range1.setStart(elem1, elem1.textContent.indexOf(_text));
           range1.setEnd(elem1, elem1.textContent.indexOf(_text) + _text.length);
           window.getSelection().removeAllRanges();
           window.getSelection().addRange(range1);
           var evt1 = document.createEvent("MouseEvents");
           evt1.initEvent("mouseup", true, true);
           elemenq.dispatchEvent(evt1);
           // $.getScript('static/js/AutointroRE.js');
           $($("span:contains('" + task.dataObj.completions[0].result[0].value.labels[0] + "')")[0].parentElement).children().hide();
       } else {
           $($("span:contains('" + task.dataObj.completions[0].result[0].value.labels[0] + "')")[0].parentElement).children().hide();
           generateOnlyMouseoverEvent(document.getElementsByClassName("Relations_item__2qMzb")[0]);
       }
    }

    if (task && task.dataObj.format_type == 1 ) {
        $(".Controls_container__LTeAA").hide();
        $('.ls-update-btn').hide();
        $('.ls-submit-btn').hide();
        $('.ls-skip-btn').hide();
        // alert("here again");
        // $(".Controls_container__LTeAA").empty();
        var Skipbtn = $('.ls-skip-btn');
        Skipbtn.html('').append("<span>Show Me more</span>");
        // $('.ls-skip-btn').hide();
        Skipbtn.on('click', function () {
            c = ls.completionStore.addCompletion({userGenerate: true});
            ls.completionStore.selectCompletion(c.id);
            $(".Controls_container__LTeAA").hide();
            $(".Controls_task__2FuYQ").hide();
            // $(".Controls_container__LTeAA").find("*").attr("disabled", true)
            // $(".Controls_container__LTeAA").children().each(function(index,element){
            //     if (index != 0) {
            //         $(element).hide();
            //     }
            // });

            //ls.setFlags({ isLoading: true });

        });
        btndiv = $(".Controls_container__LTeAA")[0];
        var btn = $('<button type="button" class="ant-btn ant-btn-primary helpBtn1"><span>Next</span></button>');
        btndiv.append(btn[0]);
        $('.helpBtn1').on('click', function () {
          c = ls.completionStore.addCompletion({userGenerate: true});
          ls.completionStore.selectCompletion(c.id);

        $(".Controls_container__LTeAA").children().each(function(index,element){
            if (index != 0) {
                $(element).hide();
            }
        });
          ls.submitCompletion();
        });
         $('.ls-skip-btn').show();
        ls.completionStore.selected.setEdit(false);
        $(".Controls_container__LTeAA").show();
        setTimeout(function () {
            if (task.dataObj.completions != null){

                let cookies_set = document.cookie;
                cookie_find_str = "exampleshown";
                if (workerId != "None") {
                  cookie_find_str = workerId +"exampleshown";
                }
                
                if (!cookies_set.includes(cookie_find_str)) {
                    q = introJs().setOptions({
                        tooltipClass: 'customTooltip',doneLabel: "Let's Start",exitOnOverlayClick: false,exitOnEsc: false,showBullets: false,showStepNumbers: false,overlayOpacity: 0.5,disableInteraction: true,
                        steps: [{
                        title: 'Welcome 👋',
                        intro: 'This shows the final result of task that you are going to do'
                        }]
                    });
                    q.start();

                    var date = new Date();
                    date.setTime(date.getTime()+(1*60*60*1000));// setting cookie for 1 hour;
                    // alert(date);
                    var expires = "; expires="+ date.toGMTString();
                    if (workerId != "None") {
                      cookie_str = "showInro" + task.dataObj.format_type.toString() + task.dataObj.layout_id.toString() +"="+workerId +"exampleshown"+expires+"; path=/";
                    }
                    else
                    {
                     cookie_str = "showInro" + task.dataObj.format_type.toString() + task.dataObj.layout_id.toString() +"=exampleshown"+expires+"; path=/"; 
                    }
                    document.cookie = cookie_str;
                }
            }
        }, (50));
    } else if (task && task.dataObj.format_type == 2) {
        setTimeout(function () {
            tmpLS = ls;
            if (task.dataObj.layout_id == 8) {
                // $.getScript('static/js/AutointroPolygon.js');
                startIntroPolygon(task.dataObj.completions[0].result, tmpLS);
            } else if(task.dataObj.layout_id == 2) {
                if (task.dataObj.batch_id == 5) {

                    // $($("span:contains('" + result[0].value.labels[0] + "')")[0].parentElement).find("*").attr("disabled", true);
                    // $($("span:contains('" + result[0].value.labels[0] + "')")[0].parentElement).children().each(function(index,element){
                    //     $(element).attr("disabled", true);
                    // });
                    startIntroRE(task.dataObj.completions[0].result, tmpLS);
                } else {
                    //alert("Bilal 4");
                    // $.getScript('static/js/AutointroNE.js');
                    startIntroNE(task.dataObj.completions[0].result, tmpLS);
                }
            } else if(task.dataObj.layout_id == 5) {
                //$.getScript('static/js/AutointroRectangle.js');
                console.log('startIntroRectangleTask:', task);
                startIntroRectangle(task.dataObj.completions[0].result, tmpLS);
            } else if(task.dataObj.layout_id == 9 || task.dataObj.layout_id == 12) {
                // $.getScript('static/js/AutointroImageClassification.js');
                startIntroImgCls(task.dataObj.completions[0].result, tmpLS);
            }
        // setTimeout(function () {
        //     tmpLS = ls;
        //     startIntro(task.dataObj.completions[0].result, tmpLS);
        //     // c = {id: ls.completionStore.completions[1].id, editable: false};
        //     // ls.completionStore.selectCompletion(c.id);
        }, (50));
    } else if (task && task.dataObj.format_type == 3) {

        $('.ls-skip-btn').hide();
        $('.ls-update-btn').hide();
        $('.ls-submit-btn').hide();
        btndiv = $(".Controls_container__LTeAA")[0];
        if ($(".helpBtn")[0] != undefined) {
            $(".helpBtn")[0].remove();
        }
        var btn = $('<button type="button" class="ant-btn ant-btn-ghost helpBtn" style="background: #52c41a; background-color: #52c41a; color: white"><span>See Answer</span></button>');
        // btn[0].appendTo(btndiv);
        btndiv.appendChild(btn[0]);
        $(".helpBtn").on('click', function(){
            tmpLS = ls;
            reRenderTask(tmpLS);
        });

        // setTimeout(function () {

        // }, (300));
    } else if (task && (task.dataObj.format_type == 6 )) {
        setTimeout(function () {
            btndiv = $(".Controls_container__LTeAA")[0];
            $('.ls-update-btn').hide()// children().first().next().html('').append ("<span>Submit </span>");
            $('.ls-submit-btn').hide();
            ls.completionStore.selected.setEdit(false);

           var Skipbtn = $('.ls-skip-btn');
            Skipbtn.on('click', function () {
                // $(".Controls_container__LTeAA").hide();
                // $(".Controls_container__LTeAA").find("*").attr("disabled", true);
                $(".Controls_container__LTeAA").children().each(function(index,element){
                    if (index != 0) {
                        $(element).hide();
                    }
                });
            });                                         //green hash #52c41a
            var btn = $('<button type="button" class="ant-btn ant-btn-secondary helpBtn" style="background: #52c41a; background-color: #52c41a; color: white"><span>Edit</span></button>');
            var submitbutton = $('<button type="button" class="ant-btn ant-btn-primary mysubmitbtn"><span role="img" aria-label="check" class="anticon anticon-check"><svg viewBox="64 64 896 896" focusable="false" class="" data-icon="check" width="1em" height="1em" fill="currentColor" aria-hidden="true"><path d="M912 190h-69.9c-9.8 0-19.1 4.5-25.1 12.2L404.7 724.5 207 474a32 32 0 00-25.1-12.2H112c-6.7 0-10.4 7.7-6.3 12.9l273.9 347c12.8 16.2 37.4 16.2 50.3 0l488.4-618.9c4.1-5.1.4-12.8-6.3-12.8z"></path></svg></span><span>Submit </span></button>');
            btndiv.append(submitbutton[0]);
            btndiv.append(btn[0]);
            submitbutton.on('click', function(){
               ls.submitCompletion();
                // $(".Controls_container__LTeAA").hide();
                // $(".Controls_container__LTeAA").find("*").attr("disabled", true)
                $(".Controls_container__LTeAA").children().each(function(index,element){
                    if (index != 0) {
                        $(element).hide();
                    }
                });
            });
            $(".helpBtn").on('click', function(){
                ls.completionStore.selected.setEdit(true);
                $(".helpBtn").hide();
                $('.mysubmitbtn').hide();
                var updatebtn = $('<button type="button" class="ant-btn ant-btn-primary myupdatebtn"><span role="img" aria-label="check-circle" class="anticon anticon-check-circle"><svg viewBox="64 64 896 896" focusable="false" class="" data-icon="check-circle" width="1em" height="1em" fill="currentColor" aria-hidden="true"><path d="M699 353h-46.9c-10.2 0-19.9 4.9-25.9 13.3L469 584.3l-71.2-98.8c-6-8.3-15.6-13.3-25.9-13.3H325c-6.5 0-10.3 7.4-6.5 12.7l124.6 172.8a31.8 31.8 0 0051.7 0l210.6-292c3.9-5.3.1-12.7-6.4-12.7z"></path><path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z"></path></svg></span><span>Update </span></button>');
                    btndiv.append(updatebtn[0]);
                    updatebtn.on('click', function (){
                        // $(".Controls_container__LTeAA").hide();
                        // $(".Controls_container__LTeAA").find("*").attr("disabled", true)
                        $(".Controls_container__LTeAA").children().each(function(index,element){
                            if (index != 0) {
                                $(element).hide();
                            }
                        });
                         ls.submitCompletion();
                })
            });
            showDemo = Cookies.get("showInro" + task.dataObj.format_type.toString() + task.dataObj.layout_id.toString());
            if (showDemo == undefined) {
                q = introJs().setOptions({
                    tooltipClass: 'customTooltip',doneLabel: "Let's Start",exitOnOverlayClick: false,exitOnEsc: false,showBullets: false,showStepNumbers: false,overlayOpacity: 0.5,disableInteraction: true,
                    steps: [{
                        title: 'Welcome 👋',
                        intro: 'Other User has done this task, Does it look okay to you? You can edit if not!'
                    }]
                });
                Cookies.set("showInro" + task.dataObj.format_type.toString() + task.dataObj.layout_id.toString(), true, { expires: 1 });
                // Cookies.remove("example");
                q.start();
            }
        }, (100));
    }

    // var matchingElement = document.querySelector("#label-studio > div > div > div > div.App_common__QaThK.ls-common > div.App_menu__X-A5N.ls-menu > div:nth-child(1) > div.ant-card-body > ul > li:nth-child(1)");
    // // alert(matchingElement);
    // matchingElement.style.display = "none";
}

function reRenderTask(ls){
    // ls.resetState();
    // ls.assignTask(response);
    // ls.initializeStore(_convertTask(response));
    // ls.updateDescription(response.description);
    let cs = ls.completionStore;
    let c;
    if (ls.completionStore.selected.id === cs.completions[0].id){
        c = {id: cs.completions[1].id, editable: false};
        cs.selectCompletion(c.id);
        if (TaskdataObj.layout_id == 2 && TaskdataObj.batch_id == 5) {
            $($("span:contains('" + result[0].value.labels[0] + "')")[0].parentElement).children().hide();
            generateOnlyMouseoverEvent(document.getElementsByClassName("Relations_item__2qMzb")[0]);
        }
    cs.selected.setupHotKeys();
        btndiv = $(".Controls_container__LTeAA")[0];
        $(".helpBtn").children().first().html('').append ("<span>Back to Task </span>");
        // parent = $(".ls-skip-btn").parent();
        // parent.children().eq(0).before(parent.children().last());
        // parent.children().eq(0).before(parent.children().last());
        // $('.ls-skip-btn').hide();
        // $('.ls-update-btn').hide();
        $('.ls-skip-btn').hide();
        $('.ls-update-btn').hide();
        $('.ls-submit-btn').hide();

        $('.mysubmitbtn').hide();
        ls.completionStore.selected.setEdit(false);
    } else {
        c = {id: cs.completions[0].id, editable: false};
        cs.selectCompletion(c.id);
        if (TaskdataObj.layout_id == 2 && TaskdataObj.batch_id == 5) {
            $($("span:contains('" + result[0].value.labels[0] + "')")[0].parentElement).children().hide();
        }
        cs.selected.setupHotKeys();
        $(".helpBtn").children().first().html('').append ("<span>See Answer </span>");
        // parent = $(".helpBtn").parent();
        // var evt = document.createEvent("MouseEvents");
        // evt.initEvent("click", true, false);
        // $("body")[0].dispatchEvent(evt);

        // parent.children().eq(0).before(parent.children().last());
        // parent.children().eq(0).before(parent.children().last());
        // parent.children().eq(0).before(parent.children().last());
        // parent.children().eq(0).before(parent.children().last());

        // $('.ls-skip-btn').show();
        // $('.ls-update-btn').show();
        $('.ls-skip-btn').hide();
        $('.ls-update-btn').hide();
        $('.ls-submit-btn').hide();
        $('.mysubmitbtn').show();


        ls.completionStore.selected.setEdit(true);
    }


    // var Skipbtn = $('.ls-skip-btn').children().first();
    // Skipbtn.html('').append ("<span>Next </span>");
    // Skipbtn.on('click', function(){
    //     c = ls.completionStore.addCompletion({ userGenerate: true });
    //     cs.selectCompletion(c.id);
    //     // ls.onSkipTask(ls);
    // });

}

const loadNext = function(ls, reset, trainingTask, batchid) {
  var url = `${API_URL.MAIN}${API_URL.PROJECT}${API_URL.NEXT}/${batchid}?${API_URL.TraingTask}${trainingTask}&${urlParam}`;
  return _loadTask(ls, url, "", reset);
};

const loadTask = function(ls, taskID, completionID, reset=false) {
  var url = `${API_URL.MAIN}${API_URL.TASKS}/${taskID}/`;
  return _loadTask(ls, url, completionID, reset);
};

const _convertTask = function(task) {
  // converts the task from the server format to the format
  // supported by the LS frontend
  if (!task) return;

  if (task.completions) {
    for (let tc of task.completions) {
      tc.pk = tc.id;
      tc.createdAgo = tc.created_ago;
      tc.createdBy = tc.created_username;
      tc.leadTime = tc.lead_time;
    }
  }

  if (task.predictions) {
    for (let tp of task.predictions) {
      tp.pk = tp.pk;
      tp.createdAgo = tp.created_ago;
      tp.createdBy = tp.created_by;
      tp.createdDate = tp.created_date;
    }
  }

  return task;
};


const LSF_SDK = function(elid, config, task, hide_skip, description, reset, response, batchid, numofPanel, _isAdmin,
                         _workerId,_hitId,_turkSubmitTo,_assignmentId,_gameid ) {

  const showHistory = task === null;  // show history buttons only if label stream mode, not for task explorer
  const batch_id = batchid;
  isAdmin = _isAdmin;
  workerId = _workerId;

  if (_workerId != "None") {
      urlParam = "workerId=" + _workerId + "&hitId=" + _hitId + "&turkSubmitTo=" + _turkSubmitTo + "&assignmentId=" + _assignmentId + "&gameid=" + _gameid;
  } else {
      urlParam = "";
  }

  const _prepDataCid = function(c, Cid) {
    var completion = {
      lead_time: (new Date() - c.loadedDate) / 1000,  // task execution time
      result: c.serializeCompletion()
    };

    completion.id = parseInt(Cid);
    const body = JSON.stringify(completion);
    return body;
  };

  const _prepData = function(c, includeId) {
    var completion = {
      lead_time: (new Date() - c.loadedDate) / 1000,  // task execution time
      result: c.serializeCompletion()
    };

    if (includeId) {
        completion.id = parseInt(c.id);
    }
    const body = JSON.stringify(completion);
    return body;
  };

  function initHistory(ls) {
      if (!ls.taskHistoryIds) {
          ls.taskHistoryIds = [];
          ls.taskHistoryCurrent = -1;
      }
  }
  function addHistory(ls, task_id, completion_id) {
      ls.taskHistoryIds.push({task_id: task_id, completion_id: completion_id});
      ls.taskHistoryCurrent = ls.taskHistoryIds.length;
  }

  var interfaces = [
      "basic",
      // "panel", // undo, redo, reset panel
      // "controls", // all control buttons: skip, submit, update
      // "submit", // submit button on controls
      // "update", // update button on controls
      //     "predictions",
      //    "predictions:menu", // right menu with prediction items
      //    "completions:menu", // right menu with completion items
      //    "completions:add-new",
      //    "completions:delete",
      //     "side-column", // entity
      //     "skip",
      //      "leaderboad",
      //      "messages",
  ];
  if (!hide_skip) {
    interfaces.push('skip');
  }

  if (numofPanel == 1) {
     interfaces.push("panel"); // undo, redo, reset panel
     interfaces.push("controls"); // all control buttons: skip, submit, update
     interfaces.push("submit"); // submit button on controls
     interfaces.push("update"); // update button on controls

      // interfaces.push("predictions");
     // interfaces.push("predictions:menu"); // right menu with prediction items
     // interfaces.push("completions:menu"); // right menu with completion items
     // interfaces.push("completions:menu"); // right menu with completion items
     // interfaces.push("completions:add-new");
     // interfaces.push("completions:delete");
     interfaces.push("side-column"); // entity
     interfaces.push("skip");
     // interfaces.push("leaderboad");
     interfaces.push("messages");
  }

  var LS = new LabelStudio(elid, {
    config: config,
    user: { pk: 1, firstName: "Awesome", lastName: "User" },

    task: _convertTask(task),
    interfaces: interfaces,
    description: description,

    onSubmitCompletion: function(ls, c) {
      ls.setFlags({ isLoading: true });
      // $(".Controls_container__LTeAA").hide();
      //   $(".Controls_container__LTeAA").find("*").attr("disabled", true)
                $(".Controls_container__LTeAA").children().each(function(index,element){
                    if (index != 0) {
                        $(element).hide();
                    }
                });

        

        console.log(ls.task.dataObj.format_type);
        console.log(ls.task.dataObj.completions[0].id);
        // console.log(ls.task);
        // console.log(ls.task["completions"][0]);
        // console.log(ls.task["completions"][0]['id']);


        // if (c.serializeCompletion().length == 0 &&  TaskdataObj.format_type == 3){
        //     $('body').toast({
        //     class: 'error',
        //     title: 'Empty Response',
        //     message: '<pre>' + "Response can not be empty!" + '</pre>',
        //     displayTime: 3000,
        //     position: 'bottom center'
        //   });
        //     ls.setFlags({ isLoading: false });
        //     setTimeout(function () {
        //         MyDOList(tmpLS, tmpLS.task);
        //     }, (200));
        //     return false ;
        // }

      let body = '';


      if (ls.task.dataObj.format_type == 6)
      {
        body = _prepDataCid(c, ls.task.dataObj.completions[0].id);

      }
      else
      {
        body = _prepData(c);

      }

      const req = Requests.poster(`${API_URL.MAIN}${API_URL.TASKS}/${ls.task.id}${API_URL.COMPLETIONS}/?${urlParam}`, body );
      
      req.then(function(httpres) {
        httpres.json().then(function(res) {
          if (res && res.id) {
              c.updatePersonalKey(res.id.toString());
              addHistory(ls, ls.task.id, res.id);
          //     $('body').toast({
          //   class: 'success',
          //   title: 'Answer Response',
          //   message: '<pre>' + "Your Answer is correct" + '</pre>',
          //   displayTime: 3000,
          //   position: 'bottom center'
          // });
          } else if (res && res.IsEmpty) {
            //alert("Bilal 4");
              $('body').toast({
            class: 'error',
            title: 'Empty Response',
            message: '<pre>' + "Response can not be empty!" + '</pre>',
            displayTime: 3000,
            position: 'bottom center'
          });

          }

          if (task) {
            ls.setFlags({ isLoading: false });
              console.log("task loaded");
                  // alert("Bilal 4");
          } else {
            loadNext(ls, true, 0, batch_id);
          }
        });
      });

      return true;
    },

    onTaskLoad: function(ls, task) {
      // render back & next buttons if there are history

      if (showHistory && ls.taskHistoryIds && ls.taskHistoryIds.length > 0) {
        var firstBlock = $('[class^=Panel_container]').children().first();
        var className = firstBlock.attr('class');
        var block = $('<div class="'+className+'"></div>');
        // prev button
        block.append('<button type="button" class="ant-btn ant-btn-ghost" ' +
                     (ls.taskHistoryCurrent > 0 ? '': 'disabled') +
                     ' onclick="window.LSF_SDK._sdk.prevButtonClick()">' +
                     '<i class="ui icon fa-angle-left"></i> Prev</button>');
        // next button
        block.append('<button type="button" class="ant-btn ant-btn-ghost"' +
                     (ls.taskHistoryCurrent < ls.taskHistoryIds.length ? '': 'disabled') +
                     ' onclick="window.LSF_SDK._sdk.nextButtonClick()">' +
                     'Next <i class="ui icon fa-angle-right"></i></button>');
        firstBlock.after(block);
      }



    },

    onUpdateCompletion: function(ls, c) {
        // $(".Controls_container__LTeAA").hide();
        // $(".Controls_container__LTeAA").find("*").attr("disabled", true)
                $(".Controls_container__LTeAA").children().each(function(index,element){
                    if (index != 0) {
                        $(element).hide();
                    }
                });
      ls.setFlags({ isLoading: true });

      const req = Requests.patch(
        `${API_URL.MAIN}${API_URL.TASKS}/${ls.task.id}${API_URL.COMPLETIONS}/${c.pk}?${urlParam}`,
        _prepData(c)
      );

      req.then(function(httpres) {
        // ls.setFlags({ isLoading: false });
        // refresh task from server
        loadTask(ls, ls.task.id, ls.completionStore.selected.id, false);
      });
    },

    onDeleteCompletion: function(ls, completion) {
      ls.setFlags({ isLoading: true });

      const req = Requests.remover(`${API_URL.MAIN}${API_URL.TASKS}/${ls.task.id}${API_URL.COMPLETIONS}/${completion.pk}/?${urlParam}`);
      req.then(function(httpres) {
        ls.setFlags({ isLoading: false });
      });
    },

    onSkipTask: function(ls) {
      ls.setFlags({ loading: true });
      // $(".Controls_container__LTeAA").hide();
      //   $(".Controls_container__LTeAA").find("*").attr("disabled", true)
                $(".Controls_container__LTeAA").children().each(function(index,element){
                    if (index != 0) {
                        $(element).hide();
                    }
                });
      var c = ls.completionStore.selected;
      var completion = _prepData(c, false);

      Requests.poster(
        `${API_URL.MAIN}${API_URL.TASKS}/${ls.task.id}${API_URL.COMPLETIONS}${API_URL.CANCEL}&${urlParam}`,
        completion
      ).then(function(response) {
        response.json().then(function (res) {
          if (res && res.id) {
            c.updatePersonalKey(res.id.toString());
            addHistory(ls, ls.task.id, res.id);
          }

          // if (task) {
          //   ls.setFlags({ isLoading: false });
            // refresh task from server
            // loadTask(ls, ls.task.id, res.id);
          // } else {
            if (ls.task.dataObj.format_type == 1) {
                // alert("here again format type 1");
                loadNext(ls,true, 1, batch_id);
            } else {
                loadNext(ls, true, 0, batch_id);
            }
          // }
        })
      });

      return true;
    },

    onGroundTruth: function(ls, c, value) {
      Requests.patch(
        `${API_URL.MAIN}${API_URL.TASKS}/${ls.task.id}${API_URL.COMPLETIONS}/${c.pk}/`,
        JSON.stringify({ honeypot: value })
      );
    },

    onLabelStudioLoad: function(ls) {
      var self = ls;
      ls.onTaskLoad = this.onTaskLoad;  // FIXME: make it inside of LSF
      ls.onPrevButton = this.onPrevButton; // FIXME: remove it in future
      initHistory(ls);
      // var xpath = "//*[@id="label-studio"]/div/div/div/div[2]/div[2]/div[1]/div[2]/ul/li[1]";
      // var matchingElement = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
      // 

      if (reset == false) {
          if (!task) {
              ls.setFlags({isLoading: true});
              loadNext(ls, false, 0, batch_id);
          // }
          } else {
            if (!task.completions || task.completions.length === 0) {
                var c = ls.completionStore.addCompletion({userGenerate: true});
                ls.completionStore.selectCompletion(c.id);
            }
            // else {
            //     ls.addUserRanks(task.userranks);
            // }
          }
      }
      // else {
      //   response.data = JSON.stringify(response.data);
      //   // ls.setFlags({isLoading: false});
      //   ls.resetState();
      //   ls.assignTask(response);
      //   cTask = _convertTask(response);
      //   ls.initializeStore(cTask);
      //
      //   let cs = ls.completionStore;
      //   let c;
      //   if (cs.predictions.length > 0) {
      //       c = ls.completionStore.addCompletionFromPrediction(cs.predictions[0]);
      //   }
      //
      //   // we are on history item, take completion id from history
      //   else if (ls.completionStore.completions.length > 0 && response.completionID) {
      //       c = {id: response.completionID};
      //   } else if (ls.completionStore.completions.length > 0 && response.completionID === 'auto') {
      //       c = {id: ls.completionStore.completions[0].id};
      //   } else {
      //       c = ls.completionStore.addCompletion({userGenerate: true});
      //   }
      //
      //   if (c.id) cs.selectCompletion(c.id);
      //   // ls.onTaskLoad(ls, ls.task);
      //     ls.setFlags({isLoading: false});
      // }
      // alert("Bilal 3");
    }
  });

  // TODO WIP here, we will move that code to the SDK
  var sdk = {
      "loadNext": function () { loadNext(LS) },
      "loadTask": function (taskID, completionID) { loadTask(LS, taskID, completionID) },
      'prevButtonClick': function() {
          LS.taskHistoryCurrent--;
          let prev = LS.taskHistoryIds[LS.taskHistoryCurrent];
          loadTask(LS, prev.task_id, prev.completion_id);
      },
      'nextButtonClick': function() {
          LS.taskHistoryCurrent++;
          if (LS.taskHistoryCurrent < LS.taskHistoryIds.length) {
            let prev = LS.taskHistoryIds[LS.taskHistoryCurrent];
            loadTask(LS, prev.task_id, prev.completion_id);
          }
          else {
            loadNext(LS, true, 0, batchid);  // new task
          }
      }
  };

  LS._sdk = sdk;

      // matchingElement.style.display = "none";
      //#label-studio > div > div > div > div.App_common__QaThK.ls-common > div.App_menu__X-A5N.ls-menu > div:nth-child(1) > div.ant-card-body > ul > li:nth-child(1)
  return LS;
};
