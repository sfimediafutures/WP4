
var app = MCorp.app("4704154345375000225");
app.options = {"markingbox": true, "pip": false, "pos": true, "pippos": true};
app.to = new TIMINGSRC.TimingObject();
app.sequencer = new TIMINGSRC.Sequencer(app.to);
app.subsequencer = new TIMINGSRC.Sequencer(app.to);

app.ready.then(function() {
  app.to.timingsrc = app.motions.private;
  app.resize();
});

app.subsequencer.on("change", evt => {
  if (evt.data) {
    let subs = document.querySelector(".subtitle");
    subs.innerHTML = evt.data;
    subs.classList.remove("hidden");
  }
})

app.subsequencer.on("remove", evt => {
    document.querySelector(".subtitle").classList.add("hidden");
});

app.load_video = function(info, videotarget) {
  app.videotarget = document.querySelector(videotarget);
  app.videotarget.pos = app.videotarget.pos || [50,50];
  let video = document.createElement("video");
  video.src = info.src;
  video.addEventListener("loadedmetadata", function() {
    app.resize();
    app.resize(document.querySelector(videotarget));            
  });
  video.classList.add("auto-resize");
  video.classList.add("maincontent");
  video.pos = [50, 50];
  video.sync = MCorp.mediaSync(video, app.to, {skew: info.offset || 0});
  document.querySelector(videotarget).appendChild(video);
};

app.load = function(url, videotarget, options) {
  app.videotarget = document.querySelector(videotarget);
  options = options || {};
  return new Promise(function(resolve, reject) {
    fetch(url)
      .then(response => response.json())
      .then(data => {
        app.manifest = data;

        app.load_video(data.video, videotarget);

        if (data.subtitles)
          data.subtitles.forEach(subtitle => {
            app.load_subs(app.subsequencer, subtitle.src);
          });

        // We load this into a sequencer lickety split
        let i = 0;
        data.cues.forEach(item => {
          if (!options.dataonly)
            item.target = videotarget;
          if(!item.end) { console.log("MISSING ITEM STOP");}
          let id = "c" + item.start.toFixed(1).replace(".","-");
          app.sequencer.addCue(id, new TIMINGSRC.Interval(item.start, item.end || item.start), item);
          i++;
        });
        resolve(data);
      });
    });
};

let moveid = 1; // We need to handle multiple moves before they stop
let move = function(element, targets, time, scene_change) {
  if (time == 0) {
    for (let target in targets) {
      element.style[target] = targets[target];
    }
    return;
  }
  moveid++;
  // targets should be a property map, e.g. {height: "80px", width: "50%"}
  time = time || 1000;
  let state = {};

  for (let target in targets) {
    state[target] = {};
    let val = target[target];
    let info = /(-?\d+)(.*)/.exec(targets[target]);
    let curinfo = /(-?\d+)(.*)/.exec(element.style[target]);
    if (!curinfo) curinfo = [0, 0, "px"];
    state[target].what = info[2];
    state[target].sval = parseInt(curinfo[1]);
    state[target].tval = parseInt(info[1]);
    state[target].val = parseInt(curinfo[1]);
    state[target].diff = state[target].tval - state[target].sval;
    // If too long, just jump
    /*
    if (scene_change) {
      element.style[target] = state[target].tval + state[target].what;
      state[target].skip = true;
    }
    */
  };
  let endtime = performance.now() + time; // app.to.pos + (time / 1000.);

  let theid = moveid;
  let update = function() {
      // Callback on time
      if (theid != moveid) {
        return;
      }
      let done = false;
      let now = performance.now(); // app.to.pos;

      if (now >= endtime) {
        for (let target in targets) {
          element.style[target] = state[target].tval + state[target].what;
        }
        return; // we're done
      }
      let cur_pos = 1 - (endtime - now) / time;
      for (let target in targets) {
        if (element.style[target] == state[target].tval + state[target].what)
          continue;

        // what's the target value supposed to be

        let v = state[target].sval + (state[target].diff * cur_pos);
        element.style[target] = Math.floor(v) + state[target].what;
      }

      //movetimeout = setTimeout(update, 100);
      requestAnimationFrame(update);
    }
    //movetimeout = setTimeout(update, 100);
  requestAnimationFrame(update);
}

app.resize = function(what) {

  if (!what) {
    let ar = document.querySelectorAll(".auto-resize");
    ar.forEach(a => app.resize(a.parentElement));
    return;
  }

  let items = what.querySelectorAll(".auto-resize");
  let width = what.clientWidth;
  let height = what.clientHeight;

  let busy = {tl: false, bl: false, tr: false, br: false, l: false, r: false};

  // Resize pip if active
  if (app.options.pip) {
    let item = document.querySelector(".pip");
    let w = item.clientWidth;
    let h = item.clientHeight;

    // First we ensure that the things inside cover the whole thing (but not more)
    let ar = w / h;
    let outer_ar = width / height;
    if (outer_ar < 1) { // Portrait
      item.classList.add("portrait");
      item.classList.remove("landscape");
    } else {
      item.classList.add("landscape");
      item.classList.remove("portrait");
    }
  }

  items.forEach(item => {

    let w = item.clientWidth;
    let h = item.clientHeight;

    // First we ensure that the things inside cover the whole thing (but not more)
    let ar = w / h;
    let outer_ar = width / height;
    let changed = false;
    if (outer_ar < ar) {  // 1) { // Portrait
      if (item.classList.contains("landscape")) changed = true;
      item.classList.add("portrait");
      item.classList.remove("landscape");
    } else {
      if (item.classList.contains("portrait")) changed = true;
      item.classList.add("landscape");
      item.classList.remove("portrait");
    }

    if (changed) {
      setTimeout(function(){app.resize(what);}, 0);
      return;
    }

    // If we're not doing positioning, just return
    if (!app.options.pos) return;

    item.pos = app.videotarget.pos;
    item.animate = app.videotarget.animate;

    // Which quadrant and halfs of the screen is this in - flag it
    let pos = app.videotarget.pos;
    if (pos[0] < 45) {
      if (pos[1] <= 60) busy.tl = true;
      if (pos[1] >= 40) busy.bl = true;
      busy.l = true;
    } else {
      if (pos[0] >= 55) {
        if (pos[1] <= 60) busy.tr = true;
        if (pos[1] >= 40) busy.br = true;
        busy.r = true;
      }
    }

    if (app.options.pip && app.options.pipskew && busy.r) {
      // We're skewing the video if interesting on the right
      // 80% of the pip
      console.log("Resizing", width, document.querySelector(".pip").clientWidth);
      width = width - (document.querySelector(".pip").clientWidth * 0.7);
      // width = width * 0.7;
    }

    // Find the offsets
    let Tx = (item.pos[0] / 100.) * w;
    let Ty = (item.pos[1] / 100.) * h;
    // Selection right corner
    let Sx = Tx - (width / 2.);
    let Sy = Ty - (height / 2.);

    // We now have the corner point, but we want the whole content to be
    // within, so don't go beyond what's necessary
    let overflow_x = w - width;
    let overflow_y = h - height;

    // maximum adjustment of the overflow, or we'll go outside
    let offset_x = -Math.max(0, Math.min(overflow_x, Sx));
    let offset_y = -Math.max(0, Math.min(overflow_y, Sy));
    move(item, {
      left: Math.floor(offset_x) + "px",
      top: Math.floor(offset_y) + "px"
    }, item.animate ? 250 : 0);

    // Markingbox position too
    if (app.options.markingbox) {
      let mbox = document.querySelector(".markingbox");
      if (mbox) {
        // Center point of box relative to visible part
        mbox.style.left = Math.floor(Tx + offset_x - (mbox.clientWidth/2.)) + "px";
        mbox.style.top = Math.floor(Ty + offset_y - (mbox.clientHeight/2.)) + "px";
      }
    }

    if (!app.options.pippos) return;

    // Put the PIP at the correct place (if applicable);
    if (app.options.pippos) {
      let pip = document.querySelector(".pip");
      // Split in left/right, not quadrants
      let positions = ["r", "l"];
      if (busy[app.lastpippos] != false) {
        // Must move it
        for (let i in positions) {
          let pos = positions[i];
          if (!busy[pos]) {
            // Move here
            if (pos == "r") {
              pip.classList.remove("pipleft");
            } else {
              pip.classList.add("pipleft");
            }
            break;
          }
        }
      }
    }
  });

}


app.set_subtitle = function(subtitle) {
  let target = document.querySelector(".subtitle");
  target.innerHTML = subtitle;
  if (!subtitle) {
    target.classList.add("hidden")
  } else {
    target.classList.remove("hidden")
    return target;
  }
}

app.set_overlay = function(data) {
  data = data || {};
  let target = document.querySelector(".overlay");
  target.querySelector(".name").innerHTML = data.name || "";
  target.querySelector(".title").innerHTML = data.title || "";

  if (!data.name) {
    target.classList.add("hidden")
  } else {
    target.classList.remove("hidden")
    return target;
  }
}

app.toggle_fullscreen = function(target, cancel) {
  if (cancel) {
    if (document.fullscreenEnabled && document.cancelFullscreen) {
      document.cancelFullscreen();
    }
    return;
  }
  target.requestFullScreen = target.requestFullScreen || target.mozRequestFullScreen  || target.webkitRequestFullScreen;
  document.cancelFullscreen = document.cancelFullscreen || document.moCancelFullScreen || document.webkitCancelFullScreen;
  target.requestFullScreen();
  if (document.fullscreenEnabled || document.mozFullscreenEnabled || document.webkitIsFullScreen) {
    console.log("Cancelling fullscreen");
    document.cancelFullscreen();
  } else {
    target.requestFullScreen();
    console.log("Requesting fullscreen");
  }
};

// Load subtitles
app.load_subs = function(sequencer, url, params) {

  var toTs = function(str) {
    var parts = str.split(":");
    return parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseFloat(parts[2])
  };

  return new Promise(function(resolve, reject) {
    fetch(url)
    .then(response => response.text())
    .then(webvtt => {
      var key;
      var start;
      var end;
      var text = "";
      var lines = webvtt.split("\n");
      for (var i=0; i<lines.length; i++) {
        var line = lines[i].trim();
        var m = /(\d\d:\d\d:\d\d.\d+)\s?-->\s?(\d\d:\d\d:\d\d.\d+)/.exec(line);
        if (m) {
          start = toTs(m[1]);
          end = toTs(m[2]);
          continue;
        }
        if (line === "") {
          // STORE IT
          if (key) {
            sequencer.addCue("sub" + key, new TIMINGSRC.Interval(start, end), text);
            key = undefined;
            text = "";
          }
          continue;
        }

        // Is this a key?
        if (/^\d+/.exec(line)) {
          key = line;
          continue;
        }

        if (key) {
          text += line + "\n";
          continue;
        }
      }
      resolve();
    }).catch(err => reject(err));
  });
};