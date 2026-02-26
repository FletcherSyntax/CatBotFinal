var robot_name, cmd_movition_ctrl, max_speed, slow_speed;
var cmd_gimbal_ctrl, cmd_gimbal_steady, cmd_arm_ctrl_ui;
var max_rate, mid_rate, min_rate, arm_default_e, arm_default_r, arm_default_z; 
var max_res, mid_res, min_res; 
var zoom_x1, zoom_x2, zoom_x4;
var pic_cap, vid_sta, vid_end;
var mc_lock, mc_unlo;
var cv_none, cv_moti, cv_face, cv_objs, cv_clor, mp_hand, cv_auto;
var mp_face, mp_pose;
var re_none, re_capt, re_reco, led_off, led_aut, led_ton, base_of, base_on;
var head_ct, base_ct;
var s_panid, release, set_mid, s_tilid;
var armZ, armR, armE;

var detect_type, led_mode, detect_react, picture_size, video_size, cpu_load;
var cpu_temp, ram_usage, pan_angle, tilt_angle, wifi_rssi, base_voltage, video_fps;
var cv_movtion_mode, base_light;

fetch('/config')
  .then(response => response.text())
  .then(yamlText => {
    try {
      const yamlObject = jsyaml.load(yamlText);
      console.log(yamlObject);
      cmd_movition_ctrl = yamlObject.cmd_config.cmd_movition_ctrl;
      cmd_gimbal_steady = yamlObject.cmd_config.cmd_gimbal_steady;
      cmd_gimbal_ctrl = yamlObject.cmd_config.cmd_gimbal_ctrl;
      cmd_arm_ctrl_ui = yamlObject.cmd_config.cmd_arm_ctrl_ui;

      max_speed = yamlObject.args_config.max_speed;
      slow_speed = yamlObject.args_config.slow_speed;
      robot_name = yamlObject.base_config.robot_name;

      max_rate  = yamlObject.args_config.max_rate;
      mid_rate  = yamlObject.args_config.mid_rate;
      min_rate  = yamlObject.args_config.min_rate;
      arm_default_e = yamlObject.args_config.arm_default_e;
      arm_default_z = yamlObject.args_config.arm_default_z;
      arm_default_r = yamlObject.args_config.arm_default_r;
      armZ = arm_default_z; 
      armR = arm_default_r;
      armE = arm_default_e;

      main_type = yamlObject.base_config.main_type;
      module_type = yamlObject.base_config.module_type;

      max_res = yamlObject.code.max_res;
      mid_res = yamlObject.code.mid_res;
      min_res = yamlObject.code.min_res;

      zoom_x1 = yamlObject.code.zoom_x1;
      zoom_x2 = yamlObject.code.zoom_x2;
      zoom_x4 = yamlObject.code.zoom_x4;

      pic_cap = yamlObject.code.pic_cap;
      vid_sta = yamlObject.code.vid_sta;
      vid_end = yamlObject.code.vid_end;

      mc_lock = yamlObject.code.mc_lock;
      mc_unlo = yamlObject.code.mc_unlo;

      cv_none = yamlObject.code.cv_none;
      cv_moti = yamlObject.code.cv_moti;
      cv_face = yamlObject.code.cv_face;
      cv_objs = yamlObject.code.cv_objs;
      cv_clor = yamlObject.code.cv_clor;
      mp_hand = yamlObject.code.mp_hand;
      cv_auto = yamlObject.code.cv_auto;
      mp_face = yamlObject.code.mp_face;
      mp_pose = yamlObject.code.mp_pose;

      re_none = yamlObject.code.re_none;
      re_capt = yamlObject.code.re_capt;
      re_reco = yamlObject.code.re_reco;
      led_off = yamlObject.code.led_off;
      led_aut = yamlObject.code.led_aut;
      led_ton = yamlObject.code.led_ton;
      base_of = yamlObject.code.base_of;
      base_on = yamlObject.code.base_on;
      head_ct = yamlObject.code.head_ct;
      base_ct = yamlObject.code.base_ct;

      s_panid = yamlObject.code.s_panid;
      release = yamlObject.code.release;
      set_mid = yamlObject.code.set_mid;
      s_tilid = yamlObject.code.s_tilid;

      detect_type = yamlObject.fb.detect_type;
      led_mode    = yamlObject.fb.led_mode;
      detect_react= yamlObject.fb.detect_react;
      picture_size= yamlObject.fb.picture_size;
      video_size  = yamlObject.fb.video_size;
      cpu_load    = yamlObject.fb.cpu_load;
      cpu_temp    = yamlObject.fb.cpu_temp;
      ram_usage   = yamlObject.fb.ram_usage;
      pan_angle   = yamlObject.fb.pan_angle;
      tilt_angle  = yamlObject.fb.tilt_angle;
      wifi_rssi   = yamlObject.fb.wifi_rssi;
      base_voltage= yamlObject.fb.base_voltage;
      video_fps   = yamlObject.fb.video_fps;
      cv_movtion_mode = yamlObject.fb.cv_movtion_mode;
      base_light  = yamlObject.fb.base_light;

      if (robot_name) {
        document.title = robot_name + " WEB CTRL";
      }
    } catch (e) {
      console.error('Error parsing YAML file:', e);
    }
  })
  .catch(error => {
    console.error('Error fetching YAML file:', error);
  });

//update photos list
function generatePhotoLink(imgname) {
    var strippedname = imgname.replace("photo_", "").replace(".jpg", "");
    var photoLink = '<li><a target="_blank" href="./pictures/' + imgname + '" ><img class="photo_img" data-filename="' +imgname + '" src="./pictures/' + imgname + '" /></a>';
    photoLink += '<p>' + strippedname + '</p>';
    photoLink += '<div class="delete_btn"><button class="normal_btn delete_btn_size normal_btn_del btn_ico"></button></div></li>';
    return photoLink;
}
function updatePhotoNames() {
    $.get('/get_photo_names', function(data) {
        var photoLinks = '';
        if (window.location.pathname === '/') {
            for (var i = 0; i < Math.min(6,data.length); i++) {
                var name = data[i];
                photoLinks += generatePhotoLink(name);
            }
            $('#photo-list').html(photoLinks);
        } else {
            for (var i = 0; i < data.length; i++) {
                var name = data[i];
                photoLinks += generatePhotoLink(name);
            }
            $('#photo-list').html(photoLinks);
        }
        $("#number-photos").text(data.length);
        //delete photo
        $("#photo-list li button").on("click", function () {
        var filename = $(this).closest("li").find("img.photo_img").data('filename');
        $.post('/delete_photo', { filename: filename }, function(response) {
            if (response.success) {
                updatePhotoNames();
            } else {
                alert("Failed to delete the file.");
            }
        });
    });
    });
}
updatePhotoNames();
// setInterval(updatePhotoNames, 2000);

function captureAndUpdate() {
    cmdSend(pic_cap,0,0);
    setTimeout(updatePhotoNames, 2000)
}

//show videos tips
function showVideosTips(){
    var videostipsbox =  $("#video-del-tips");
    videostipsbox.css("opacity", "1");
    videostipsbox.css("transform", `translate(-50%, -100%)`);
    setTimeout(function() {
        videostipsbox.removeAttr("style");
    }, 2000);
}

//update videos list
function generateVideoLink(vname) {
    var strippedname = vname.replace("video_", "").replace(".mp4", "");
    var videoList = '<li><a target="_blank" data-filename="' + vname + '" href="./videos/' + vname +'">';
    videoList += '<p>' + strippedname + '</p>';
    videoList += '<div><div class="delete_btn_size normal_btn_play btn_ico"></div></div></a>';
    videoList += '<div class="delete_btn"><div class="delete_btn_size normal_btn_del btn_ico"></div></div></li>';
    return videoList;
}
function updateVideoList() {
    $.get('/get_video_names', function(data) {
        var videosLists = '';
        if (window.location.pathname === '/') {
            for (var i = 0; i < Math.min(6,data.length); i++) {
                var name = data[i];
                videosLists += generateVideoLink(name);
            }
            $('#video-list').html(videosLists);
        } else {
            for (var i = 0; i < data.length; i++) {
                var name = data[i];
                videosLists += generateVideoLink(name);
            }
            $('#video-list').html(videosLists);
        }
        $("#number-videos").text(data.length);
        //delete videos
        $("#video-list li div.normal_btn_del").on("click", function () {
        var filename = $(this).closest("li").find("a").data('filename');
        $.post('/delete_video', { filename: filename }, function(response) {
            if (response.success) {
                updateVideoList();
                showVideosTips();
            } else {
                alert("Failed to delete the video.");
                }
            });
        });
    });
}
updateVideoList();


//video pixel
var listItems = $("#video_pixel_btn_list").children("li");
listItems.on("click", function () {
    var innertext = $(this).text();
    $("#video_pixel_btn").text(innertext);
    $("#video_pixel_btn_list").css("display", "none");
    setTimeout(function () {
        $("#video_pixel_btn_list").removeAttr("style");
    }, 10);  
});

//record function
var isRecording = false;
var originalText = "Record";
var timerInterval;
var seconds = 0;
var minutes = 0;
function updateTimer() {
    seconds++;
    if (seconds === 60) {
        seconds = 0;
        minutes++;
    }
    var formattedTime = (minutes < 10 ? "0" : "") + minutes + ":" + (seconds < 10 ? "0" : "") + seconds;
    $("#record-btn").text(formattedTime);
}
$(document).ready(function () {
    $("#record-btn").click(function () {
        if (!isRecording) {
            cmdSend(vid_sta,0,0);
            $(this).css("color", "#FF8C8C");
            $(this).removeClass("video_btn_record");
            $(this).addClass("video_btn_stop");
            isRecording = true;
            $(this).text("00:00");
            timerInterval = setInterval(updateTimer, 1000);
        } else {
            cmdSend(vid_end,0,0);
            $(this).removeClass("video_btn_stop");
            $(this).addClass("video_btn_record");
            $(this).text(originalText);
            isRecording = false;
            clearInterval(timerInterval);
            seconds = 0;
            minutes = 0;
            $(this).css("color", "");
            updateVideoList();
        }
    });
});

//zoom
var zoomx = 1;
$("#zoom_btn").click(function(){
    var zoomNum  = document.getElementById("zoom-num");
    switch(zoomx){
        case 0: cmdSend(zoom_x1,0,0);
        zoomNum.innerHTML = "1x" 
        break;
        case 1: cmdSend(zoom_x2,0,0);
        zoomNum.innerHTML = "2x" 
        break;
        case 2: cmdSend(zoom_x4,0,0);
        zoomNum.innerHTML = "4x" 
        break;
    }
    zoomx = (zoomx + 1) % 3;
});

//joy stick function
var largeCircle = $("#ctrl_base");
var smallCircle = $("#ctrl_base div");
var minifyTimeout;
var isEnlarged = false;
var isMouseUp = false;
function enlargeJoyStick(){
    setTimeout(() => {
        isEnlarged = true;
    }, 98);
    largeCircle.removeClass("ctrl_base_s");
    smallCircle.removeClass("ctrl_stick_s");
    largeCircle.addClass("ctrl_base_l");
    smallCircle.addClass("ctrl_stick_l");
}
function minifyJoyStick(){
    isEnlarged = false;
    isMouseUp = false;
    largeCircle.removeClass("ctrl_base_l");
    smallCircle.removeClass("ctrl_stick_l");
    largeCircle.addClass("ctrl_base_s");
    smallCircle.addClass("ctrl_stick_s");
    
}
largeCircle.on("click", function(e){
    clearTimeout(minifyTimeout);
    enlargeJoyStick();
});

largeCircle.on("mousedown touchstart", function(){
    isMouseUp = false;
    clearTimeout(minifyTimeout);
    enlargeJoyStick();
});
$(document).on("mouseup touchend", function(){
    isMouseUp = true;
    if (isEnlarged) {
        minifyTimeout = setTimeout(minifyJoyStick, 2000);
    }
});
largeCircle.on("mouseenter", function(){
    clearTimeout(minifyTimeout);
});
largeCircle.on("mouseleave", function() {
    if (isMouseUp && isEnlarged) {
        minifyTimeout = setTimeout(minifyJoyStick, 2000);
    }
});


const base = document.getElementById('ctrl_base');
const stick = document.getElementById('ctrl_stick');
let isDragging = false;
let stickStartX = 0;
let stickStartY = 0;

var stickSendX = 0;
var stickSendY = 0;

var stickLastX = 0;
var stickLastY = 0;
// JoyStick actions for pc
try {
    stick.addEventListener('mousedown', (e) => {
        isDragging = true;
        stick.style.transition = 'none';
        const stickRect = stick.getBoundingClientRect();
        stickStartX = e.clientX - stickRect.left - stickRect.width / 2;
        stickStartY = e.clientY - stickRect.top - stickRect.height / 2;
        stickLastX = stickSendX;
        stickLastY = stickSendY;
    });
} catch(e) {
    console.log(e);
}
document.addEventListener('mousemove', (e) => {
    if (isDragging && isEnlarged) {
        moveStick(e);
    }
});
document.addEventListener('mouseup', () => {
    isDragging = false;
    try {
        stick.style.transition = '0.3s ease-out';
        stick.style.transform = 'translate(-50%, -50%)';
        base.style.border = '';
    } catch(e) {
        console.log(e);
    }
});
// JoyStick actions for mobile devices
try {
    stick.addEventListener('touchstart', (e) => {
        e.preventDefault();
        isDragging = true;
        stick.style.transition = 'none';
        const touch = e.touches[0];
        const stickRect = stick.getBoundingClientRect();
        stickStartX = touch.clientX - stickRect.left - stickRect.width / 2;
        stickStartY = touch.clientY - stickRect.top - stickRect.height / 2;
        stickLastX = stickSendX;
        stickLastY = stickSendY;
    });
} catch(e) {
    console.log(e);
}
document.addEventListener('touchmove', (e) => {
    e.preventDefault();
    if (isDragging && isEnlarged) {
        const touch = e.touches[0];
        moveStick(touch);
    }
});
try {
    stick.addEventListener('touchend', (e) => {
        //e.preventDefault();
        isDragging = false;
        stick.style.transition = '0.3s ease-out';
        stick.style.transform = 'translate(-50%, -50%)';
        base.style.border = '';
    });
} catch(e) {
    console.log(e);
}
function moveStick(event) {
    const baseRect = base.getBoundingClientRect();
    const stickRect = stick.getBoundingClientRect();
    const baseRectHalfW = baseRect.width / 2;
    const baseRectHalfH = baseRect.height / 2;

    const centerX = baseRect.left + baseRectHalfW;
    const centerY = baseRect.top + baseRectHalfH;

    const deltaX = event.clientX - centerX - stickStartX;
    const deltaY = event.clientY - centerY - stickStartY;

    const distance = Math.min(baseRectHalfW, Math.sqrt(deltaX ** 2 + deltaY ** 2));
    const angle = Math.atan2(deltaY, deltaX);

    const stickX = centerX + distance * Math.cos(angle);
    const stickY = centerY + distance * Math.sin(angle);

    const stickmovex = stickX - centerX - stickRect.width /2;
    const stickmovey = stickY - centerY - stickRect.height /2;

    stick.style.transform = `translate(${stickmovex}px, ${stickmovey}px)`;

    if (distance == baseRect.width / 2) {
        base.style.border = '2px solid #4FF5C0';
    } else {
        base.style.border = '';
    }

    stickSendX = stickLastX + deltaX;
    stickSendY = stickLastY + deltaY;

    // joyStickCtrl(deltaX, deltaY);
    joyStickCtrl(stickSendX, stickSendY);
}


function pointInCircle(radius, x, y) {
    var distance = Math.sqrt(x * x + y * y);

    if (distance <= radius) {
        return { x: x, y: y };
    } else {
        var angle = Math.atan2(y, x);
        var newX = radius * Math.cos(angle);
        var newY = radius * Math.sin(angle);
        return { x: newX, y: newY };
    }
}
document.addEventListener('mousewheel', (e) => {
    if (isDragging && isEnlarged) {
        var delta = e.deltaY || e.detail || e.wheelDelta;
        e.preventDefault();
        if (delta > 0) {
            // console.log("down");
            armE = armE - 5;
            if (armE < 60) {
                armE = 60;
            }
        } else {
            // console.log("up");
            armE = armE + 5;
            if (armE > 450) {
                armE = 450;
            }
        }
        // cmdSend(145, stickExtend, 0);
        var armLimit = pointInCircle(510, armE, armZ);
        armE = armLimit.x;
        armZ = armLimit.y;
        cmdJsonCmd({"T":cmd_arm_ctrl_ui,"E":armE,"Z":armZ,"R":armR});
    }
}, { passive: false });
function joyStickCtrl(inputX, inputY) {
    if (module_type == 1) {
        var x_cmd = Math.max(-180, Math.min(inputX/7, 180));
        console.log(inputY);
        // cmdSend(144, -inputX/7, -inputY/2);
        var armLimit = pointInCircle(510, armE, -inputY/2);
        armE = armLimit.x;
        armZ = armLimit.y;
        armR = -inputX/7;
        cmdJsonCmd({"T":cmd_arm_ctrl_ui,"E":armE,"Z":armZ,"R":armR});

        RotateAngle = document.getElementById("Pan").innerHTML = x_cmd.toFixed(2);
        var panScale = document.getElementById("pan_scale");
        panScale.style.transform = `rotate(${-RotateAngle}deg)`;
    } else {
        if (steady_mode == true) {
            inputX = 0;
        }
        var x_cmd = Math.max(-180, Math.min(inputX/2.5, 180));
        var y_cmd = Math.max(-30, Math.min(-inputY/2.5, 90));

        if (steady_mode == false) {
            cmdJsonCmd({"T":cmd_gimbal_ctrl,"X":inputX/2.5,"Y":-inputY/2.5,"SPD":0,"ACC":128});
        } else {
            steadyCtrl(1, inputY);
        }

        RotateAngle = document.getElementById("Pan").innerHTML = x_cmd.toFixed(2);
        var panScale = document.getElementById("pan_scale");
        panScale.style.transform = `rotate(${-RotateAngle}deg)`;

        var tiltNum = document.getElementById("Tilt");
        var tiltNumPanel = tiltNum.getBoundingClientRect();
        var tiltNumMove = tiltNum.innerHTML = y_cmd.toFixed(2);;

        var pointer = document.getElementById('tilt_scale_pointer');
        var tiltScaleOut = document.getElementById('tilt_scale');
        var tiltScaleBase = tiltScaleOut.getBoundingClientRect();
        var tiltScalediv = document.getElementById('tilt_scalediv');
        var tiltScaleDivBase = tiltScalediv.getBoundingClientRect();
        var pointerMoveY = tiltScaleBase.height/135;
        pointer.style.transform = `translate(${tiltScaleDivBase.width}px, ${pointerMoveY*(90 - tiltNumMove)-tiltNumPanel.height/2}px)`;
    }
}


//seetting page
function confirmSetPanID() {
    if (confirm("Make sure that you have already DISCONNECT the wire of the Tilt Servo")) {
        cmdSend(s_panid, 0, 0);
    }
}
function confirmRelease() {
    if (confirm("You will unlock the torque lock, then you can manually adjust the angle of the two servos.")) {
        cmdSend(release, 0, 0);
    }
}
function confirmMiddleSet() {
    if (confirm("Set the current position as the middle position.")) {
        cmdSend(set_mid, 0, 0);
    }
}
function confirmSetTiltID() {
    if (confirm("If you didn't disconnect the Tilt Servo in step 1, then both servo IDs will be set to 2 after you click the [Set Pan ID] button. Only in this case, you need to click [Set Tilt ID] to restore both servo IDs to 1, then repeat the entire setup process!")) {
        cmdSend(s_tilid, 0, 0);
    }
}




function cmdFill(rawInfo, fillInfo) {
    document.getElementById(rawInfo).value = document.getElementById(fillInfo).innerHTML;
}

function jsonSendFb() {
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function() {
        if (this.readyState == 4 && this.status == 200) {
          document.getElementById("fbInfo").innerHTML =
          this.responseText;
        }
    };
    xhttp.open("GET", "jsfb", true);
    xhttp.send();
}
function jsonSend() {
    var xhttp = new XMLHttpRequest();
    xhttp.open("GET", "js?json="+document.getElementById('jsonData').value, true);
    xhttp.send();
    jsonSendFb();
}


//remove buttons class
function removeButtonsClass(buttons) {
    for (var i = 0; i < buttons.length; i++) {
        buttons[i].classList.remove("ctl_btn_active");
    }
}
//remove all ico class
function removeAllIcoClass(ElName){
    while (ElName.classList.length > 0) {
        ElName.classList.remove(ElName.classList.item(0));
    }
}

var socketJson = io(location.protocol + '//' + location.host + '/json');
socketJson.emit('json', {'T':1,'L':0,'R':0})

var socket = io(location.protocol + '//' + location.host + '/ctrl');
socket.emit('request_data');

var light_mode = 0;
var cv_heartbeat_stop_flag = false;
socket.on('update', function(data) {
    if (data[base_voltage] != 0) {
        // console.log(data[detect_react]);
    } else {
        return;
    }
    try {
        var baseBtn = document.getElementById("base_led_ctrl_btn");
        var BButtons = baseBtn.getElementsByTagName("button");
        removeButtonsClass(BButtons);
        if (data[base_light] == 0) {
            BButtons[0].classList.add("ctl_btn_active");
        } else if (data[base_light] != 0){
            BButtons[1].classList.add("ctl_btn_active");
        }

        var advCBtn = document.getElementById("adv_cv_ctrl_btn");
        var CButtons = advCBtn.getElementsByTagName("button");
        removeButtonsClass(CButtons);

        var advFBtn = document.getElementById("adv_cv_funcs_btn");
        var FButtons = advFBtn.getElementsByTagName("button");
        removeButtonsClass(FButtons);

        var mpBtn = document.getElementById("mp_funcs_btn");
        var MPButtons = mpBtn.getElementsByTagName("button");
        removeButtonsClass(MPButtons);

        var dtIco = document.getElementById("DT");
        var dTypeBtn = document.getElementById("d_type_btn");
        var DTbuttons = dTypeBtn.getElementsByTagName("button");
        removeAllIcoClass(dtIco);
        removeButtonsClass(DTbuttons);
        if (data[detect_type] == cv_none) {
            dtIco.classList.add("feed_ico", "feed_ico_none");
            DTbuttons[0].classList.add("ctl_btn_active");
        } else if (data[detect_type] == cv_moti) {
            dtIco.classList.add("feed_ico", "feed_ico_movtion");
            DTbuttons[1].classList.add("ctl_btn_active");
        } else if (data[detect_type] == cv_face) {
            dtIco.classList.add("feed_ico", "feed_ico_face");
            DTbuttons[2].classList.add("ctl_btn_active");
        } else if (data[detect_type] == cv_auto) {
            CButtons[2].classList.add("ctl_btn_active");
        } else if (data[detect_type] == cv_objs) {
            FButtons[0].classList.add("ctl_btn_active");
        } else if (data[detect_type] == cv_clor) {
            FButtons[1].classList.add("ctl_btn_active");
        } else if (data[detect_type] == mp_hand) {
            FButtons[2].classList.add("ctl_btn_active");
        } else if (data[detect_type] == mp_face) {
            MPButtons[0].classList.add("ctl_btn_active");
        } else if (data[detect_type] == mp_pose) {
            MPButtons[1].classList.add("ctl_btn_active");
        }

        if (data[detect_type] == cv_auto && cv_heartbeat_stop_flag == false) {
            cv_heartbeat_stop_flag = true;
        } else if (cv_heartbeat_stop_flag == true) {
            cv_heartbeat_stop_flag = false;
        }

        if (data[cv_movtion_mode] == true) {
            CButtons[0].classList.add("ctl_btn_active");
        } else if (data[cv_movtion_mode] == false) {
            CButtons[1].classList.add("ctl_btn_active");
        }

        var drIco = document.getElementById("DR");
        var DReactionBtn = document.getElementById("d_reaction_btn");
        var DRbuttons = DReactionBtn.getElementsByTagName("button");
        removeButtonsClass(DRbuttons);
        if (data[detect_react] == re_none) {
            removeAllIcoClass(drIco);
            drIco.classList.add("feed_ico", "feed_ico_none");
            DRbuttons[0].classList.add("ctl_btn_active");
        } else if (data[detect_react] == re_capt) {
            removeAllIcoClass(drIco);
            drIco.classList.add("feed_ico", "feed_ico_capture");
            DRbuttons[1].classList.add("ctl_btn_active");
        } else if (data[detect_react] == re_reco) {
            removeAllIcoClass(drIco);
            drIco.classList.add("feed_ico", "feed_ico_record");
            DRbuttons[2].classList.add("ctl_btn_active");
        }

        lightMode = document.getElementById("MODE");
        var lightCtrlBtn = document.getElementById("light_ctrl_btn");
        var lbuttons = lightCtrlBtn.getElementsByTagName("button");
        removeButtonsClass(lbuttons);
        light_mode = data[led_mode];
        if (data[led_mode] == 0) {
            lightMode.innerHTML = "OFF";
            lbuttons[0].classList.add("ctl_btn_active");
        } else if (data[led_mode] == 1) {
            lightMode.innerHTML = "AUTO";
            lbuttons[1].classList.add("ctl_btn_active");
        } else if (data[led_mode] == 2) {
            lightMode.innerHTML = "ON";
            lbuttons[2].classList.add("ctl_btn_active");
        }

        document.getElementById("CPU").innerHTML = data[cpu_load] + "%";
        document.getElementById("tem").innerHTML = data[cpu_temp].toFixed(1) + " ℃";
        document.getElementById("RAM").innerHTML = data[ram_usage] + "%";
        document.getElementById("rssi").innerHTML = data[wifi_rssi] + " dBm";
        document.getElementById("fps").innerHTML = data[video_fps].toFixed(1);
        
        document.getElementById("photos-size").innerHTML = data[picture_size] + " MB";
        document.getElementById("videos-size").innerHTML = data[video_size] + " MB";

        document.getElementById("v_in").innerHTML = data[base_voltage].toFixed(1);
        
        var element = document.getElementById("b_state");
        element.classList.remove("baterry_state", "baterry_state1", "baterry_state2", "baterry_state3");
        if (data[base_voltage] >= 10.5) {
            element.classList.add("baterry_state");
        } else if (data[base_voltage] >= 10) {
            element.classList.add("baterry_state","baterry_state3");
        } else if (data[base_voltage] >= 9.5) {
            element.classList.add("baterry_state","baterry_state2");
        } else if (data[base_voltage] < 9.5) {
            element.classList.add("baterry_state","baterry_state1");
        }
    } catch(e) {
        console.log(e);
    }

});

var heartbeat_left  = 0;
var heartbeat_right = 0;
var speed_rate = 0.3;
var defaultSpeed = speed_rate;
let lastTimeCmdSend = Date.now();;
let lastArgsCmdSend;
function cmdSend(inputA, inputB, inputC){
    const now = Date.now();
    if (!lastArgsCmdSend || inputA != lastArgsCmdSend || now - lastTimeCmdSend >= 10) {
        var jsonData = {
            "A":inputA,
            "B":inputB,
            "C":inputC
        };
        console.log(jsonData);
        socket.send(JSON.stringify(jsonData));
        lastArgsCmdSend = inputA;
        lastTimeCmdSend = now;
    }
}

function cmdJsonCmd(jsonData){
    console.log(jsonData);
    if (jsonData.T == cmd_movition_ctrl) {
        heartbeat_left = jsonData.L;
        heartbeat_right = jsonData.R;
        jsonData.L = heartbeat_left * speed_rate;
        jsonData.R = heartbeat_right * speed_rate;
    }
    socketJson.emit('json', jsonData);
}

function speedCtrl(inputSpd){
    speed_rate = inputSpd;
    defaultSpeed = speed_rate;
    var spdCtrlBtn = document.getElementById("speed_ctrl_btn");
    var spdbuttons = spdCtrlBtn.getElementsByTagName("button");
    removeButtonsClass(spdbuttons);
    if (speed_rate <= 0.30) {
        spdbuttons[0].classList.add("ctl_btn_active");
    } else if (speed_rate > 0.30 && speed_rate < 0.70) {
        spdbuttons[1].classList.add("ctl_btn_active");
    } else if (speed_rate >= 0.70) {
        spdbuttons[2].classList.add("ctl_btn_active");
    }
}

var steady_mode = false;
function steadyCtrl(inputCmd, inputBias){
    inputBias = -inputBias*0.4;
    var steadyCtrlBtn = document.getElementById("steady_ctrl_btn");
    var steadybuttons = steadyCtrlBtn.getElementsByTagName("button");
    removeButtonsClass(steadybuttons);
    if (inputCmd == 0) {
        steadybuttons[0].classList.add("ctl_btn_active");
        steady_mode = false;
        cmdJsonCmd({"T":cmd_gimbal_steady,"s":0,"y":inputBias});
    } else if (inputCmd == 1) {
        steadybuttons[1].classList.add("ctl_btn_active");
        steady_mode = true;
        cmdJsonCmd({"T":cmd_gimbal_steady,"s":1,"y":inputBias});
    }
}

var heartbeat_send_flag = true;
function heartbeat_send(){
    if (socketJson.connected && heartbeat_send_flag && !cv_heartbeat_stop_flag) {
        cmdJsonCmd({'T':cmd_movition_ctrl,'L':heartbeat_left,'R':heartbeat_right});
    }
}
setInterval(heartbeat_send, 2000);



var isInputFocused = false;

var moveKeyMap = {
    16: 'shift', // acce
    49: 'low',
    50: 'middle',
    51: 'fast',
    65: 'left',   // A
    87: 'forward', // W
    83: 'backward', // S
    68: 'right', // D
}
var move_buttons = {
    shift: 0,
    low: 0,
    middle: 0,
    fast: 0,
    forward: 0,
    backward: 0,
    left: 0,
    right: 0,
}
function moveProcess() {
    var forwardButton  = move_buttons.forward;
    var backwardButton = move_buttons.backward;
    var leftButton  = move_buttons.left;
    var rightButton = move_buttons.right;

    // Speed Ctrl
    if (move_buttons.low == 1){
        speedCtrl(min_rate);
    } else if (move_buttons.middle == 1){
        speedCtrl(mid_rate);
    } else if (move_buttons.fast == 1){
        speedCtrl(max_rate);
    }

    if(move_buttons.shift == 1) {
        speed_rate = max_rate;
        var spdCtrlBtn = document.getElementById("speed_ctrl_btn");
        var spdbuttons = spdCtrlBtn.getElementsByTagName("button");
        removeButtonsClass(spdbuttons);
        if (speed_rate <= 0.33) {
            spdbuttons[0].classList.add("ctl_btn_active");
        } else if (speed_rate > 0.33 && speed_rate < 0.66) {
            spdbuttons[1].classList.add("ctl_btn_active");
        } else if (speed_rate >= 0.66) {
            spdbuttons[2].classList.add("ctl_btn_active");
        }
    } else {
        speedCtrl(defaultSpeed);
    }

    // Movtion Ctrl
    if (forwardButton == 0 && backwardButton == 0 && leftButton == 0 && rightButton == 0) {
        heartbeat_left  =  0;
        heartbeat_right =  0;
    }else if (forwardButton == 1 && backwardButton == 0 && leftButton == 0 && rightButton == 0){
        heartbeat_left  =  max_speed;
        heartbeat_right =  max_speed;
    }else if (forwardButton == 0 && backwardButton == 1 && leftButton == 0 && rightButton == 0){
        heartbeat_left  = -max_speed;
        heartbeat_right = -max_speed;
    }else if (forwardButton == 0 && backwardButton == 0 && leftButton == 1 && rightButton == 0){
        heartbeat_left  = -max_speed;
        heartbeat_right =  max_speed;
    }else if (forwardButton == 0 && backwardButton == 0 && leftButton == 0 && rightButton == 1){
        heartbeat_left  =  max_speed;
        heartbeat_right = -max_speed;
    }else if (forwardButton == 1 && backwardButton == 0 && leftButton == 1 && rightButton == 0){
        heartbeat_left  =  slow_speed;
        heartbeat_right =  max_speed;
    }else if (forwardButton == 1 && backwardButton == 0 && leftButton == 0 && rightButton == 1){
        heartbeat_left  =  max_speed;
        heartbeat_right =  slow_speed;
    }else if (forwardButton == 0 && backwardButton == 1 && leftButton == 1 && rightButton == 0){
        heartbeat_left  = -slow_speed;
        heartbeat_right = -max_speed;
    }else if (forwardButton == 0 && backwardButton == 1 && leftButton == 0 && rightButton == 1){
        heartbeat_left  = -max_speed;
        heartbeat_right = -slow_speed;
    }

    cmdJsonCmd({'T':cmd_movition_ctrl,'L':heartbeat_left,'R':heartbeat_right});
}
function updateMoveButton(key, value) {
    move_buttons[key] = value;
}




var keyMap = {
    67: "c",
    82: 'r',
    69: 'e',
    70: 'f',
    71: 'g',
    72: 'h',
    73: 'i',
    75: 'k',
    77: 'm',
    74: 'j',
    76: 'l',
    79: 'o',
    84: 't',
    85: 'u'
};

var ctrl_buttons = {
    c: 0,
    r: 0,
    e: 0,
    f: 0,
    g: 0,
    h: 0,
    i: 0,
    k: 0,
    m: 0,
    j: 0,
    l: 0,
    o: 0,
    t: 0,
    u: 0
};

function updateButton(key, value) {
    ctrl_buttons[key] = value;
}

function cmdProcess() {
    // Base Light Ctrl
    if (ctrl_buttons.f == 1){
        cmdSend(base_ct, 0, 0);
    }

    // Photo Capture
    if (ctrl_buttons.e == 1){
        cmdSend(pic_cap, 0, 0);
    }

    // Function Ctrl
    if (ctrl_buttons.r == 1){
        cmdSend(head_ct, 0, 0);
    }

    // Gimbal Ctrl
    if (ctrl_buttons.i == 1){
        stickSendY -= 10;
        if (stickSendY < -225) {
            stickSendY = -225;
        }
        joyStickCtrl(stickSendX, stickSendY);
    } else if (ctrl_buttons.k == 1){
        stickSendY += 10;
        if (stickSendY > 115) {
            stickSendY = 115;
        }
        joyStickCtrl(stickSendX, stickSendY);
    } else if (ctrl_buttons.j == 1){
        stickSendX -= 10;
        if (stickSendX < -450) {
            stickSendX = -450;
        }
        joyStickCtrl(stickSendX, stickSendY);
    } else if (ctrl_buttons.l == 1){
        stickSendX += 10;
        if (stickSendX > 450) {
            stickSendX = 450;
        }
        joyStickCtrl(stickSendX, stickSendY);
    } else if (ctrl_buttons.h == 1){
        joyStickCtrl(0, 0);
    }

    // Gimbal/Arm Steady Ctrl
    if (ctrl_buttons.u == 1){
        steadyCtrl(0, stickSendY);
    } else if (ctrl_buttons.o == 1){
        steadyCtrl(1, stickSendY);
    } else if (ctrl_buttons.c == 1){
        lookAhead();
    } else if (ctrl_buttons.g == 1){
        cmdJsonCmd({"T":106,"cmd":3.14,"spd":0,"acc":0});
    } else if (ctrl_buttons.t == 1){
        cmdJsonCmd({"T":106,"cmd":1.57,"spd":0,"acc":0});
    }
}

document.onkeydown = function (event) {
    if (isInputFocused) {
        return;
    }
    var key = keyMap[event.keyCode];
    var moveKey = moveKeyMap[event.keyCode];
    if (key && ctrl_buttons[key] === 0) {
        updateButton(key, 1);
        cmdProcess();
    } else if (moveKey && move_buttons[moveKey] === 0) {
        updateMoveButton(moveKey, 1);
        moveProcess();
    }
}

document.onkeyup = function (event) {
    if (isInputFocused) {
        return;
    }
    var key = keyMap[event.keyCode];
    var moveKey = moveKeyMap[event.keyCode];
    if (key && ctrl_buttons[key] === 1) {
        updateButton(key, 0);
        cmdProcess();
    } else if (moveKey && move_buttons[moveKey] === 1) {
        updateMoveButton(moveKey, 0);
        moveProcess();
    }
}

function lookAhead() {
    if (module_type == 1) {
        armZ = arm_default_z; 
        armR = arm_default_r;
        armE = arm_default_e;
        stickLastX = 0;
        stickLastY = -arm_default_z;
        stickSendX = 0;
        stickSendY = -arm_default_z;
        cmdJsonCmd({"T":cmd_arm_ctrl_ui,"E":armE,"Z":armZ,"R":armR});
    } else {
        armZ = arm_default_z; 
        armR = arm_default_r;
        armE = arm_default_e;
        stickLastX = 0;
        stickLastY = 0;
        stickSendX = 0;
        stickSendY = 0;
        joyStickCtrl(0, 0);
    }
}

document.getElementById('sendButton').addEventListener('click', function() {
    var command = document.getElementById('commandInput').value;
    fetch('/send_command', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: 'command=' + encodeURIComponent(command)
    })
    .then(response => response.json())
    .then(data => {
        console.log(data);
        // 处理响应
    })
    .catch(error => {
        console.error('Error:', error);
    });
});

document.getElementById('commandInput').addEventListener('focus', function() {
    isInputFocused = true;
});

document.getElementById('commandInput').addEventListener('blur', function() {
    isInputFocused = false;
});


// gamepad ctrl functions
var gp_x = 0.00;
var gp_z = 0.00;
var last_gp_x = 0.00;
var last_gp_z = 0.00;
var gp_turnning = 3.14;

var last_gp_lt1 = false;
var last_gp_lt2 = false;
var last_gp_rt1 = false;
var last_gp_rt2 = false;

var last_gp_record = false;
var last_gp_picture = false;
var last_gp_telepresence = false;

var gp_pt_x = 0;
var gp_pt_y = 0;
var last_gp_pt_x = 0;
var last_gp_pt_y = 0;
var gp_pt_speed = 1.0;

window.addEventListener("gamepadconnected", function(e) {
  console.log("gamepad connected:" + e.gamepad.index);
  heartbeat_send_flag = false;
});

window.addEventListener("gamepaddisconnected", function(e) {
  console.log("gamepad disconnected:" + e.gamepad.index);
  heartbeat_send_flag = true;
});

function logButtons(gamepad) {
  gamepad.buttons.forEach((button, index) => {
    console.log(`button ${index}: ${button.pressed ? 'pressed' : 'released'}`);
  });
}

function logAxes(gamepad) {
  gamepad.axes.forEach((axis, index) => {
    console.log(`axis ${index}: ${axis}`);
  });
}

function readGamepad() {
  var gamepads = navigator.getGamepads ? navigator.getGamepads() : [];
  for (var i = 0; i < gamepads.length; i++) {
    var gp = gamepads[i];
    if(gp) {
      // Uncomment to debug your controller mapping:
      // logButtons(gp);
      // logAxes(gp);

      // === RIGHT JOYSTICK FOR STEERING (tank-style) ===
      // Right stick: axes[2] (X) and axes[3] (Y)
      var stickY = -gp.axes[3]; // Forward/back (inverted so up = forward)
      var stickX = gp.axes[2];  // Left/right turn
      
      // Apply dead zones
      if (Math.abs(stickY) < 0.15) stickY = 0;
      if (Math.abs(stickX) < 0.15) stickX = 0;

      // Convert to tank drive (L/R motor speeds)
      // Joystick position directly controls speed (no trigger needed)
      // Cap at 0.5 to avoid motor stall
      var maxMotorSpeed = 0.5;
      var leftMotor = (stickY + stickX) * maxMotorSpeed;
      var rightMotor = (stickY - stickX) * maxMotorSpeed;
      
      // Clamp to maxMotorSpeed
      leftMotor = Math.max(-maxMotorSpeed, Math.min(maxMotorSpeed, leftMotor));
      rightMotor = Math.max(-maxMotorSpeed, Math.min(maxMotorSpeed, rightMotor));

      // Send movement command if changed (using same format as on-screen buttons)
      if (leftMotor != last_gp_x || rightMotor != last_gp_z) {
        cmdJsonCmd({"T":cmd_movition_ctrl,"L":leftMotor,"R":rightMotor});
        last_gp_x = leftMotor;
        last_gp_z = rightMotor;
      }

      // === A BUTTON (button 0) - TAKE PICTURE ===
      if (last_gp_picture != gp.buttons[0].pressed) {
        if (gp.buttons[0].pressed) {
          console.log("Gamepad: Taking picture");
          cmdSend(pic_cap, 0, 0);
        }
        last_gp_picture = gp.buttons[0].pressed;
      }

      // === Y BUTTON (button 3) - TOGGLE TELEPRESENCE ===
      if (last_gp_telepresence != gp.buttons[3].pressed) {
        if (gp.buttons[3].pressed) {
          console.log("Gamepad: Toggling telepresence");
          if (typeof toggleTelepresence === 'function') {
            toggleTelepresence();
          }
        }
        last_gp_telepresence = gp.buttons[3].pressed;
      }

      // === BUTTON 9 (Start/Menu) - TOGGLE RECORDING ===
      if (last_gp_record != gp.buttons[9].pressed) {
        if (gp.buttons[9].pressed) {
          if (!isRecording) {
            cmdSend(vid_sta, 0, 0);
            isRecording = true;
          } else {
            cmdSend(vid_end, 0, 0);
            isRecording = false;
          }
        }
        last_gp_record = gp.buttons[9].pressed;
      }
    }
  }
  window.requestAnimationFrame(readGamepad);
}

window.requestAnimationFrame(readGamepad);


document.getElementById('open_jupyter').addEventListener('click', function() {
    var currentUrl = window.location.href;
    var newUrl = currentUrl.replace(/:(\d+)/, ':8888');
    window.open(newUrl, '_blank');
});


// WiFi Manager
var wifiConnectTarget = '';

function wifiShowMessage(msg, isError) {
    var el = document.getElementById('wifi-message');
    el.textContent = msg;
    el.style.display = 'block';
    el.style.color = isError ? '#FF8C8C' : '#4FF5C0';
    setTimeout(function() { el.style.display = 'none'; }, 5000);
}

function wifiUpdateStatus() {
    fetch('/wifi/status')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            document.getElementById('wifi-mode').textContent = data.mode || '--';
            document.getElementById('wifi-ssid').textContent = data.ssid || '--';
            document.getElementById('wifi-ip').textContent = data.ip || '--';
            var hBtn = document.getElementById('wifi-hotspot-btn');
            if (data.mode === 'AP') {
                hBtn.textContent = 'Hotspot Active';
                hBtn.classList.add('ctl_btn_active');
            } else {
                hBtn.textContent = 'Switch to Hotspot';
                hBtn.classList.remove('ctl_btn_active');
            }
        })
        .catch(function(e) { console.error('WiFi status error:', e); });
}

function wifiScan() {
    var spinner = document.getElementById('wifi-scan-spinner');
    var netDiv = document.getElementById('wifi-networks');
    var netList = document.getElementById('wifi-network-list');
    netDiv.style.display = 'block';
    spinner.style.display = 'inline';
    netList.innerHTML = '';

    fetch('/wifi/scan')
        .then(function(r) { return r.json(); })
        .then(function(networks) {
            spinner.style.display = 'none';
            if (networks.length === 0) {
                netList.innerHTML = '<li class="wifi_net_empty">No networks found</li>';
                return;
            }
            var html = '';
            for (var i = 0; i < networks.length; i++) {
                var n = networks[i];
                var sigBars = n.signal > 75 ? '||||' : n.signal > 50 ? '|||' : n.signal > 25 ? '||' : '|';
                var lockIcon = n.security ? ' [secured]' : '';
                html += '<li class="wifi_net_item" data-ssid="' + n.ssid.replace(/"/g, '&quot;') + '" data-secured="' + (n.security ? '1' : '0') + '">';
                html += '<span class="wifi_net_name">' + n.ssid + '</span>';
                html += '<span class="wifi_net_detail">' + sigBars + ' ' + n.signal + '%' + lockIcon + '</span>';
                html += '</li>';
            }
            netList.innerHTML = html;

            var items = netList.querySelectorAll('.wifi_net_item');
            for (var j = 0; j < items.length; j++) {
                items[j].addEventListener('click', function() {
                    var ssid = this.getAttribute('data-ssid');
                    var secured = this.getAttribute('data-secured') === '1';
                    wifiConnect(ssid, secured);
                });
            }
        })
        .catch(function(e) {
            spinner.style.display = 'none';
            wifiShowMessage('Scan failed: ' + e, true);
        });
}

function wifiConnect(ssid, secured) {
    wifiConnectTarget = ssid;
    if (secured) {
        // Check if we have a saved profile first
        fetch('/wifi/saved')
            .then(function(r) { return r.json(); })
            .then(function(saved) {
                var hasSaved = false;
                for (var i = 0; i < saved.length; i++) {
                    if (saved[i] === ssid) { hasSaved = true; break; }
                }
                if (hasSaved) {
                    wifiDoConnect(ssid, '');
                } else {
                    document.getElementById('wifi-connect-ssid').textContent = ssid;
                    document.getElementById('wifi-password-input').value = '';
                    document.getElementById('wifi-password-dialog').style.display = 'block';
                    document.getElementById('wifi-password-input').focus();
                }
            })
            .catch(function() {
                document.getElementById('wifi-connect-ssid').textContent = ssid;
                document.getElementById('wifi-password-input').value = '';
                document.getElementById('wifi-password-dialog').style.display = 'block';
                document.getElementById('wifi-password-input').focus();
            });
    } else {
        wifiDoConnect(ssid, '');
    }
}

function wifiConnectConfirm() {
    var pw = document.getElementById('wifi-password-input').value;
    document.getElementById('wifi-password-dialog').style.display = 'none';
    wifiDoConnect(wifiConnectTarget, pw);
}

function wifiConnectCancel() {
    document.getElementById('wifi-password-dialog').style.display = 'none';
    wifiConnectTarget = '';
}

function wifiDoConnect(ssid, password) {
    wifiShowMessage('Connecting to ' + ssid + '...', false);
    fetch('/wifi/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'ssid=' + encodeURIComponent(ssid) + '&password=' + encodeURIComponent(password)
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        wifiShowMessage(data.message, !data.success);
        if (data.success) {
            document.getElementById('wifi-networks').style.display = 'none';
            // Delay status update to allow network to settle
            setTimeout(wifiUpdateStatus, 3000);
        }
    })
    .catch(function(e) { wifiShowMessage('Connection error: ' + e, true); });
}

function wifiSwitchHotspot() {
    var mode = document.getElementById('wifi-mode').textContent;
    if (mode === 'AP') {
        wifiShowMessage('Already in hotspot mode', false);
        return;
    }
    wifiShowMessage('Switching to hotspot...', false);
    fetch('/wifi/hotspot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: ''
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        wifiShowMessage(data.message, !data.success);
        if (data.success) {
            document.getElementById('wifi-networks').style.display = 'none';
            setTimeout(wifiUpdateStatus, 3000);
        }
    })
    .catch(function(e) { wifiShowMessage('Hotspot error: ' + e, true); });
}

// Update WiFi status on page load and periodically
if (document.getElementById('wifi-mode')) {
    wifiUpdateStatus();
    setInterval(wifiUpdateStatus, 10000);
}

// Allow Enter key in password field
var wifiPwInput = document.getElementById('wifi-password-input');
if (wifiPwInput) {
    wifiPwInput.addEventListener('keydown', function(e) {
        if (e.keyCode === 13) { wifiConnectConfirm(); }
    });
    wifiPwInput.addEventListener('focus', function() { isInputFocused = true; });
    wifiPwInput.addEventListener('blur', function() { isInputFocused = false; });
}

function shutdownRobot() {
    if (confirm('Are you sure you want to shut down CatBot?')) {
        fetch('/shutdown', { method: 'POST' })
            .then(() => alert('CatBot is shutting down...'));
    }
}

function rebootRobot() {
    if (confirm('Are you sure you want to reboot CatBot?')) {
        fetch('/reboot', { method: 'POST' })
            .then(() => alert('CatBot is rebooting...'));
    }
}
