
var app = MCorp.app("4704154345375000225");
app.to = new TIMINGSRC.TimingObject();
app.sequencer = new TIMINGSRC.Sequencer(app.to);

app.ready.then(function() {
  app.to.timingsrc = app.motions.private;
  app.resize();
});


app.load_video = function(info, videotarget) {
    let video = document.createElement("video");
    video.src = info.src;
    video.addEventListener("loadedmetadata", function() {
      app.resize();
      app.resize(document.querySelector(videotarget));            
    });
    video.classList.add("auto-resize");
    video.pos = [50, 50];
    video.sync = MCorp.mediaSync(video, app.to, {skew: info.offset || 0});
    document.querySelector(videotarget).appendChild(video);
};

app.load = function(url, videotarget) {
  fetch(url)
    .then(response => response.json())
    .then(data => {
      console.log("Got data", data);

      app.load_video(data.video, videotarget);

      // We load this into a sequencer lickety split
      let i = 0;
      data.cues.forEach(item => {
        item.target = videotarget;
        app.sequencer.addCue("itm" + i, new TIMINGSRC.Interval(item.start, item.stop || item.start), item);
        i++;
      });
    });
};

let moveid = 1; // We need to handle multiple moves before they stop
let move = function(element, targets, time) {
  if (time == 0) {
    for (let target in targets) {
      element.style[target] = targets[target];
    }
    return;
  }
  moveid++;
  // targets should be a property map, e.g. {height: "80px", width: "50%"}
  time = time || 1000;
  console.log("MOVE", element, targets, time);
  let state = {};

  for (let target in targets) {
    state[target] = {};
    let val = target[target];
    let info = /(-?\d+)(.*)/.exec(targets[target]);
    console.log("Checking", target, element.style[target]);
    let curinfo = /(-?\d+)(.*)/.exec(element.style[target]);
    if (!curinfo) curinfo = [0, 0, "px"];
    state[target].what = info[2];
    state[target].sval = parseInt(curinfo[1]);
    state[target].tval = parseInt(info[1]);
    state[target].val = parseInt(curinfo[1]);
    state[target].diff = state[target].tval - state[target].sval;
    console.log("TARGET", target, state[target]);
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
          console.log("END", target, element.style[target])
        }
        return; // we're done
      }

      let cur_pos = 1 - (endtime - now) / time;
      for (let target in targets) {
        if (element.style[target] == state[target].tval + state[target].what)
          continue;

        // what's the target value supposed to be

        let v = state[target].sval + (state[target].diff * cur_pos);
        element.style[target] = v + state[target].what;
        console.log("SET", target, v, element.style[target], state[target].tval + state[target].what);
      }

      //movetimeout = setTimeout(update, 100);
      requestAnimationFrame(update);
    }
    //movetimeout = setTimeout(update, 100);
  requestAnimationFrame(update);
}

app.resize = function(what) {

  console.log("RESIZE", what);
  if (!what) {
    let ar = document.querySelectorAll(".auto-resize");
    ar.forEach(a => app.resize(a.parentElement));
    return;
  }

  let items = what.querySelectorAll(".auto-resize");
  let width = what.clientWidth;
  let height = what.clientHeight;

  items.forEach(item => {

    let w = item.clientWidth;
    let h = item.clientHeight;

    // First we ensure that the things inside cover the whole thing (but not more)
    let ar = h / w;
    let outer_ar = height / width;
    if (ar < outer_ar) { // outer is wider
      item.style.height = "100%";
      item.style.width = "";
    } else {
      // outer is narrower
      item.style.width = "100%";
      item.style.height = "";
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
      left: offset_x + "px",
      top: offset_y + "px"
    }, 0);
    //item.style.left = offset_x + "px";
    //item.style.top = offset_y + "px";

    console.log("dbg:", Tx, Ty, Sx, Sy, overflow_x, overflow_y, offset_x, offset_y);
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