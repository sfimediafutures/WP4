var rubberDuck = function(target, options) {

    let API = {};
    if (typeof(target) == "string")
      API.targetElement = document.querySelector(target);
    else
      API.targetElement = target;

    let default_options = {
        track: true,
        markingbox: false,
        pip: false,
        pos: true,
        pippos: true,
        rendersubs: true,
        advancedsubs: true,
        keyboard: true,
        index: true,
        tts: false,
        tts_lang: "no",
        tts_autopause: true,
        controls: true,
        synstolk: true,
        audioon: false
    };
    let __autopaused = false;
    let _is_speaking = false;

    let get_hash = function(str) {

        var hash = 0;
        if (str.length == 0) {
            return hash;
        }
        for (var i = 0; i < str.length; i++) {
            var char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = (hash & hash) & 0xffffff; // Convert to 24bit integer
        }
        return hash;
    }


    API.options = options;
    for (let d in default_options) {
        if (API.options[d] === undefined)
            API.options[d] = default_options[d]
    }
    API.to = new TIMINGSRC.TimingObject();

    if (options.mcorp_appid) {
        API.app = MCorp.app(options.mcorp_appid);
    }

    API.play = function() {
        if (API.videoElement)
            API.videoElement.play();

        if (API.targetElement.querySelector(".overlay")) {
            API.targetElement.querySelector(".overlay").style.display = "none";
        }

        if (options.mcorp_appid) {
            // API.app = MCorp.app(options.mcorp_appid);
            API.app.ready.then(function() {

                if (API.videoElement) {
                    console.log("Video loaded, and mcorp app ready - check entry");
                    let hash = get_hash(API.videoElement.src);
                    console.log("HASH", hash, API.app.motions.entry.pos);
                    if (API.app.motions.entry.pos != hash) {
                        API.app.motions.entry.update(hash);
                        API.app.motions.private.update(0,1);
                    }
                }

                console.log("Online sync ready");
                API.to.timingsrc = API.app.motions.private;
                API.resize();
            });
        } else {
            API.to.update({position: 0, velocity:1});
        }

        // Default audio on?
        if (API.options.audioon) {
          let snd = API.targetElement.querySelector("#btnsound");
          let soundOn = snd.classList.contains("active");
          if (!soundOn) snd.click();
        }

    }

    API.sequencer = new TIMINGSRC.Sequencer(API.to);
    API.subsequencer = new TIMINGSRC.Sequencer(API.to);
    API.idxsequencer = new TIMINGSRC.Sequencer(API.to);

    // ***************** Controls ******************'
    let ctrltimeout;
    let showControls = function(visible) {
      if (!options.controls) return;
      clearTimeout(ctrltimeout);

        let ctrl = API.targetElement.querySelector(".controls");
        if (visible === undefined) {
            // Auto
            if (ctrl.classList.contains("hidden")) {
                // Show but set timeout
                ctrltimeout = setTimeout(function() {
                    showControls(false);
                }, 5000);
                // Show it
                ctrl.classList.remove("hidden");
            } else {
                ctrl.classList.add("hidden");
            }
        } else {
            if (visible) {
                ctrl.classList.remove("hidden");
            } else {
                ctrl.classList.add("hidden");
            }
        }
    }

    let toggle_sound = function(evt) {
      let snd = API.targetElement.querySelector("#btnsound");
      let soundOn = !snd.classList.contains("active");
            console.log("SoundOn:", soundOn);
            if (!soundOn) {
                API.videoElement.muted = true;
                snd.classList.remove("active");
                toggle_synstolk(null, false);
            } else {
                API.videoElement.muted = false;
                snd.classList.add("active");
                toggle_synstolk(null, false);
            }
    };


    let toggle_synstolk = function(evt, force) {
        if (!API.synstolkElement && force !== undefined) return;

        let btn = API.targetElement.querySelector("#btnsynstolk");
        let isOn = !btn.classList.contains("active");
        console.log("isOn:", isOn);
        if (!isOn || force == false) {
            // Check if sound is on
            let snd = API.targetElement.querySelector("#btnsound");
            let soundOn = snd.classList.contains("active");
            if (API.synstolkElement) {
                API.synstolk_sync.pause()
                API.synstolkElement.muted = true;
                API.synstolkElement.pause();
                API.videoElement.muted = !soundOn;
            } else {
                // Enable TTS here if we don't have a separate sound track
                API.tts = true;
            }

            btn.classList.remove("active");
        } else {
            // Syns tolk is on - mute video and get the synstolk going
            if (API.synstolkElement) {
                API.videoElement.muted = true;
                API.synstolk_sync.pause(false);
                API.synstolkElement.muted = false;                
            } else {
                API.tts = false;
            }
            btn.classList.add("active");
        }
    };


    let btns = {
        "btntrack": function(evt) {
            evt.preventDefault();
            let isActive = !evt.srcElement.classList.contains("active");
            options.markingbox = isActive;
            console.log("Markings is now", isActive);
            if (isActive) {
                API.targetElement.querySelector(".markingbox").classList.remove("hidden");
                evt.srcElement.classList.add("active");
            } else {
                API.targetElement.querySelector(".markingbox").classList.add("hidden");
                evt.srcElement.classList.remove("active");
            }
        },
        "btnpip": function(evt) {
            evt.preventDefault();
            API.options.pip = !evt.srcElement.classList.contains("active");
            let pip = API.targetElement.querySelector(".pip");
            if (API.options.pip) evt.srcElement.classList.add("active")
            else evt.srcElement.classList.remove("active");
            if (API.options.pip) {
                if (!pip.sync) {
                    pip.sync = MCorp.mediaSync(pip, API.to, {
                        skew: -6
                    });
                }
                pip.classList.remove("hidden");
            } else {
                if (pip) pip.classList.add("hidden");
            }
            API.resize();
        },
        "btnpippos": function(evt) {
            evt.preventDefault();
            API.options.pippos = !evt.srcElement.classList.contains("active");
            API.options.pipskew = !API.options.pippos;
            if (API.options.pippos) {
                evt.srcElement.classList.add("active");
                API.targetElement.querySelector(".pip").classList.remove("pipfixed");
            } else {
                evt.srcElement.classList.remove("active");
                API.targetElement.querySelector(".pip").classList.add("pipfixed");
                API.targetElement.querySelector(".pip").classList.remove("pipleft"); // in case it's on the left
            }
            API.resize();
        },
        "btnpos": function(evt) {
            evt.preventDefault();
            API.options.pos = !evt.srcElement.classList.contains("active");
            //API.options.pipskew = API.options.pos;
            if (API.options.pos) {
                evt.srcElement.classList.add("active");
            } else {
                evt.srcElement.classList.remove("active");
                // In case we used pipskew, return the width of the outer container
                API.videoElement.style.width = "100%";
                API.resize();
            }
            API.resize();
        },
        "btnstart": function(evt) {
            evt.preventDefault();
            API.to.update({
                position: 0,
                velocity: 0
            })
        },
        "btnrev": function(evt) {
            evt.preventDefault();
            API.to.update({
                position: Math.max(0, API.to.pos - 15)
            })
        },
        "btnplay": function(evt) {
            evt.preventDefault();
            API.to.update({
                velocity: 1
            })
        },
        "btnpause": function(evt) {
            evt.preventDefault();
            API.to.update({
                velocity: 0
            })
        },
        "btnff": function(evt) {
            evt.preventDefault();
            API.to.update({
                position: API.to.pos + 10
            })
        },

        "btnfs": function(evt) {
            evt.preventDefault();
            API.toggle_fullscreen(API.targetElement);
        },
        "btnsound": function(evt) {
            evt.preventDefault();
            toggle_sound(evt);
        },
        "btnsynstolk": function(evt) {
            evt.preventDefault();
            toggle_synstolk(evt);
        },
        "btn_nrktegnspraak": function(evt) {
            evt.preventDefault();
            let on = !evt.srcElement.classList.contains("active");
            let pip = API.targetElement.querySelector(".pip");
            let vid = API.videoElement;
            console.log("NRK tegnspraak:", on);
            if (on) {
                if (!pip.sync) {
                    pip.sync = MCorp.mediaSync(pip, API.to, {
                        skew: -6
                    });
                }
                pip.classList.remove("hidden");
                pip.classList.add("pipfixed");

                // No auto tracking
                API.options.pip = true;
                API.options.pippos = false;
                API.options.pos = false;
                API.targetElement.querySelector("#btnpippos i").classList.remove("active");
                API.targetElement.querySelector("#btnpip i").classList.add("active");
                API.targetElement.querySelector("#btnpos i").classList.remove("active");

                console.log("Removing a bunch of classes");
                vid.classList.remove("auto-resize");
                vid.classList.remove("portrait");
                vid.classList.add("landscape");

                evt.srcElement.classList.add("active");
                // Make video container smaller
                API.videoElement.style.width = "80%";
                API.videoElement.style.height = "80%";
                vid.style.left = "0px";
                vid.style.width = "100%";
                vid.style.top = "0px";
            } else {
                vid.classList.add("auto-resize");
                evt.srcElement.classList.remove("active");
                pip.classList.remove("pipfixed");
                pip.style.width = "";
                pip.style.position = "";
                pip.style.right = "";
                pip.style.bottom = "";
                API.videoElement.style.width = "100%";
                API.videoElement.style.height = "100%";
                vid.style.left = "";
                vid.style.maxHeight = "";
                vid.style.maxWidth = "";
                vid.style.top = "";
                vid.style.height = "";
                vid.style.width = "";
                API.resize();
            }
        },
        "btn_nrktegnspraak_zoom": function(evt) {
            evt.preventDefault();
            let on = !evt.srcElement.classList.contains("active");
            let pip = API.targetElement.querySelector(".pip");
            let vid = API.videoElement;
            console.log("NRK tegnspraak:", on);
            if (on) {
                if (!pip.sync) {
                    pip.sync = MCorp.mediaSync(pip, API.to, {
                        skew: -6
                    });
                }
                pip.classList.remove("hidden");
                pip.classList.add("pipfixed");
                // No auto tracking
                API.options.pip = true;
                API.options.pippos = false;
                API.targetElement.querySelector("#btnpippos i").classList.remove("active");
                API.targetElement.querySelector("#btnpip i").classList.add("active");

                evt.srcElement.classList.add("active");
                // Make PIP fixed on the side
                // Make video container smaller
                API.videoElement.style.width = "80%";
            } else {
                pip.classList.remove("pipfixed");
                evt.srcElement.classList.remove("active");
                API.videoElement.style.width = "100%";
                API.resize();
            }
        }
    }

    for (let btn in btns) {
        let opt = API.options[btn.substr(3)];
        if (opt != false) {
          let b = btn;
          if (API.targetElement.querySelector("#" + btn))
              API.targetElement.querySelector("#" + btn).addEventListener("click", evt => {evt.stopPropagation(); btns[b](evt)});
        } else if (!opt) {
            if (API.targetElement.querySelector("#" + btn)) API.targetElement.querySelector("#" + btn).style.display = "none";
        }
    }


    API.to.on("change", function() {
      if (!options.controls) return;
        if (this.vel == 0) {
            clearTimeout(ctrltimeout);
            showControls(true);
            API.targetElement.querySelector("#btnplay i").classList.remove("hidden");
            API.targetElement.querySelector("#btnpause i").classList.add("hidden");
        } else {
            showControls(false);
            API.targetElement.querySelector("#btnpause i").classList.remove("hidden");
            API.targetElement.querySelector("#btnplay i").classList.add("hidden");
        }
    });

    // ***************** Subtitles - either "normal" or "advanced" ***************
    if (API.options.rendersubs) {
        API.subsequencer.on("change", evt => {
            let subs = API.targetElement.querySelector(".subtitle");
            if (evt.new.data && typeof(evt.new.data) == "string") {
                subs.innerHTML = "<span>" + evt.new.data.replace("\n", "<br>") + "</span>";
            } else {
                if (!API.options.advancedsubs) {
                    subs.innerHTML = "<span>" + evt.new.data.text.replace("\n", "<br>") + "</span>";
                } else {
                    // More advanced subtitle, make it here
                    try {
                        API._render_advanced_sub(evt.new, subs);
                    } catch (e) { 
                        console.log("Advanced render failed", e);
                    }
                }
            }
            subs.classList.remove("hidden");
        })

        API.subsequencer.on("remove", evt => {
            who = evt.old.data.who;
            if (who == "scene") { // || who == "info") {
                // This is a bit of information, so it's in a different spot
                API.targetElement.querySelector(".infobox").classList.add("hidden");
                return;
            }

            // Simple subs - just remove it
            if (!API.options.advancedsubs) {
                API.targetElement.querySelector(".subtitle").classList.add("hidden");
                return;
            }

            API.targetElement.querySelectorAll(".subtitle #" + evt.key).forEach(i => API.targetElement.querySelector(".subtitle").removeChild(i));
        });
    }

    // ***************************** TTS engine ****************
    if (API.options.tts) {
        API.speak = function(text, voice, force) {
            if (API.synstolkElement || !API.targetElement.querySelector("#btnsynstolk").classList.contains("active")) 
                return;


            console.log("SPEAK", text);
            return new Promise(function(resolve, reject) {
              if (!force && API.videoElement.muted) {console.log("NOPE", force); return};  // No talking when muted
                let utterance = new SpeechSynthesisUtterance(text);
                utterance.voice = API.tts_voices[voice || 0];
                utterance.onend = function() {
                  _is_speaking--;

                  if (API.options.tts_autopause && __autopaused) {
                    __autopaused = false;
                    app.to.update({velocity: 1});
                  }
                  resolve();
                };
                _is_speaking++;
                console.log(API.tts_voices, voice || 0, utterance.voice);
                console.log("Speaking", text, "in voice", utterance.voice);
                let s = speechSynthesis.speak(utterance);
            });
        }

        API.tts_voices = [];
        API.tts_ready = new Promise(function(resolve, reject) {
            speechSynthesis.onvoiceschanged = function() {
                let v = speechSynthesis.getVoices();
                speechSynthesis.getVoices().forEach(voice => {
                    if (voice.lang.startsWith(API.options.tts_lang)) {
                        if (API.tts_voices.indexOf(voice) == -1) {
                            API.tts_voices.push(voice);
                        }
                    };
                });
                console.log("Loaded", API.tts_voices.length, "voices");
                if (API.tts_voices.length > 0) {
                    // API.speak("Ready", 0);
                    console.log("READY");
                    resolve(API.tts_voices);
                }
            }
        });
    }
    // Load a video file into the video target
    API.load_video = function(info) {
        videotarget = API.targetElement;
        if (!videotarget) return;
        let video = document.createElement("video");
        video.src = info.src;
        video.addEventListener("loadedmetadata", function() {
            console.log("RESIZE");
            API.resize();
            API.resize(videotarget);
        });
        video.classList.add("auto-resize");
        video.classList.add("maincontent");
        video.pos = [50, 50];
        video.sync = MCorp.mediaSync(video, API.to, {
            skew: info.offset || 0
        });
        API.videoElement = video;
        API.videoElement.pos = API.videoElement.pos || [50, 50];
        videotarget.appendChild(video);
    };

    // Load iframe index
    API.load_index = function(url) {
        return new Promise(function(resolve, reject) {
            fetch(url)
                .then(response => response.json())
                .then(data => {
                    API.index = data;

                    // We load these, we use the next frame start as end, and we remember the reference
                    // to the previous and next iframes too for easy lookup
                    console.log("Loading", data.iframes.length, "iframes into index");
                    for (let i = 0; i < data.iframes.length; i++) {
                        let item = {
                            prev: parseFloat(data.iframes[i - 1]),
                            current: parseFloat(data.iframes[i]),
                            next: parseFloat(data.iframes[i + 1])
                        };
                        end = item.current + 1000;
                        if (item.next) end = item.next;
                        let id = "i" + item.current.toFixed(1).replace(".", "-");
                        API.idxsequencer.addCue(id, new TIMINGSRC.Interval(item.current, end), item);
                    }
                    resolve(data);
                });
        });

    }

    API.load_synstolk = function(url) {
        if (!API.synstolkElement) {
            API.synstolkElement = document.createElement("audio");
            API.synstolk_sync = MCorp.mediaSync(API.synstolkElement, API.to);
        }
        API.synstolkElement.src = url;
        API.synstolkElement.muted = false;
        API.synstolk_sync.pause(true);
        console.log("Synstolk loaded");
    }

    // Load a manifest
    API.load = function(url, videotarget, options) {
        if (!API.videoElement) {
            // Bind click to toggle controls
            API.targetElement.addEventListener("click", evt => {
              showControls();
            });

            API.targetElement.addEventListener("dblclick", evt => {
                API.toggle_fullscreen(API.targetElement);
            });
        }
        API.videoElement = document.querySelector(videotarget);
        options = options || {};
        return new Promise(function(resolve, reject) {
            fetch(url)
                .then(response => response.json())
                .then(data => {
                    API.manifest = data;
                    if (API.videoElement)
                        API.load_video(data.video, videotarget);

                    let s = data.subtitles;
                    if (!API.options.advancedsubs && data.normalsubtitles)
                        s = data.normalsubtitles;

                    if (s)
                        console.log("Loading subtitles");

                    s.forEach(subtitle => {
                        if (subtitle.src.indexOf(".json") > -1) {
                            API.load_json_subs(API.subsequencer, subtitle.src, subtitle);
                        } else {
                            API.load_subs(API.subsequencer, subtitle.src);
                        }
                    });

                    if (data.pip && API.options.pip) {
                        API.targetElement.querySelector(".pip").src = data.pip.src;
                        API.targetElement.querySelectorAll(".pipctrl").forEach(p => p.style.display = "inline-block");
                    } else {
                      // Disable pip stuff
                      API.targetElement.querySelectorAll(".pipctrl").forEach(p => p.style.display = "none");
                    }

                    if (data.cast) {
                        fetch(data.cast)
                            .then(response => response.json())
                            .then(response => API.cast = response);
                    } else {
                        API.cast = {};
                    }

                    // Do we also have synstolk audio?
                    if (data.synstolk) {
                        API.load_synstolk(data.synstolk);
                    } else {
                        // Disable button
                        if (API.targetElement.querySelector("#btnsynstolk"))
                            API.targetElement.querySelector("#btnsynstolk").classList.add("hidden");
                    }

                    if (data.index && API.options.index) {
                        API.load_index(data.index);
                    }

                    if (data.aux) {
                        fetch(data.aux)
                            .then(response => response.json())
                            .then(response => {
                                response.forEach(item => {
                                    API.sequencer.addCue(String(Math.random()), new TIMINGSRC.Interval(item.start, item.end), item);
                                });
                            });
                    }

                    if (data.dc) {
                        try {
                            console.log("Using datacannon")
                            API.dcannon = new DataCannon("wss://nlive.no/dc", [API.sequencer]);
                            API.dcannon.ready.then(function() {
                                API.dcannon.subscribe(data.dc)
                            });
                        } catch (e) {
                            console.log("DC suggested but can't be used");
                        }
                    } else {
                        // We load this into a sequencer lickety split
                        data.cues = data.cues || [];
                        let i = 0;
                        data.cues.forEach(item => {
                            if (!options.dataonly)
                                item.target = videotarget;
                            if (!item.end) {
                                console.log("MISSING ITEM STOP");
                            }
                            let id = "c" + item.start.toFixed(1).replace(".", "-");
                            API.sequencer.addCue(id, new TIMINGSRC.Interval(item.start, item.end || item.start), item);
                            i++;
                        });
                    }

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
        };
        let endtime = performance.now() + time; // API.to.pos + (time / 1000.);

        let theid = moveid;
        let update = function() {
                // Callback on time
                if (theid != moveid) {
                    return;
                }
                let done = false;
                let now = performance.now(); // API.to.pos;

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

    // Handle resizing things
    API.resize = function(what) {
        if (what == document.querySelector("body")) throw new Error("Resize body!");
        if (!what) {
            let ar = API.targetElement.querySelectorAll(".auto-resize");
            ar.forEach(a => API.resize(a.parentElement));
            return;
        }

        let items = what.querySelectorAll(".auto-resize");
        let width = what.clientWidth;
        let height = what.clientHeight;

        let busy = {
            tl: false,
            bl: false,
            tr: false,
            br: false,
            l: false,
            r: false
        };

        // Resize pip if active
        if (API.options.pip) {
            let item = API.targetElement.querySelector(".pip");
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
            if (outer_ar < ar) { // 1) { // Portrait
                if (item.classList.contains("landscape")) changed = true;
                item.classList.add("portrait");
                item.classList.remove("landscape");
            } else {
                if (item.classList.contains("portrait")) changed = true;
                item.classList.add("landscape");
                item.classList.remove("portrait");
            }

            if (changed) {
                setTimeout(function() {
                    API.resize(what);
                }, 0);
                return;
            }

            // If we're not doing positioning, just return
            if (!API.options.pos) return;

            if (!API.targetElement) return;  //  || !API.targetElement.pos) return;
            item.pos = API.targetElement.pos || [50, 50];
            item.animate = API.targetElement.animate;

            // Which quadrant and halfs of the screen is this in - flag it
            let pos = API.targetElement.pos || [50, 50];
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

            if (API.options.pip && API.options.pipskew && busy.r) {
                // We're skewing the video if interesting on the right
                // 80% of the pip
                width = width - (API.targetElement.querySelector(".pip").clientWidth * 0.7);
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
            if (1 || API.options.markingbox) {
                let mbox = API.targetElement.querySelector(".markingbox");
                if (mbox) {
                    // Center point of box relative to visible part
                    mbox.style.left = Math.floor(Tx + offset_x - (mbox.clientWidth / 2.)) + "px";
                    mbox.style.top = Math.floor(Ty + offset_y - (mbox.clientHeight / 2.)) + "px";
                } else {
                  console.log("***Missing markingbox");
                }
            } else {
                console.log("Markingbox not enabled");
            }

            if (!API.options.pippos) return;

            // Put the PIP at the correct place (if applicable);
            if (API.options.pippos) {
                let pip = API.targetElement.querySelector(".pip");
                // Split in left/right, not quadrants
                let positions = ["r", "l"];
                if (busy[API.lastpippos] != false) {
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

    window.addEventListener("resize", function() {
        setTimeout(app.resize, 0);
    });


    API.set_subtitle = function(subtitle) {
        let target = API.targetElement.querySelector(".subtitle");
        target.innerHTML = subtitle;
        if (!subtitle) {
            target.classList.add("hidden")
        } else {
            target.classList.remove("hidden")
            return target;
        }
    }

    let set_overlay = function(data) {
        data = data || {};
        let target = API.targetElement.querySelector(".overlay");
        target.querySelector(".name").innerHTML = data.name || "";
        target.querySelector(".title").innerHTML = data.title || "";

        if (!data.name) {
            target.classList.add("hidden")
        } else {
            target.classList.remove("hidden")
            return target;
        }
    }

    API.toggle_fullscreen = function(target, cancel) {
      target = API.targetElement;
        if (cancel) {
            if (document.fullscreenEnabled && document.cancelFullscreen) {
                document.cancelFullscreen();
            }
            return;
        }
        target.requestFullScreen = target.requestFullScreen || target.mozRequestFullScreen || target.webkitRequestFullScreen;
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

    // ********************  Keyboard mapping ************
    if (options.keyboard) {
        document.querySelector("body").addEventListener("keydown", evt => {
            let delta = 15;
            if (evt.ctrlKey) delta = 60;
            if (evt.shiftKey) delta = 1;

            if (evt.keyCode == 32) {
                evt.preventDefault();
                if (app.to.vel == 0) {
                    app.to.update({
                        velocity: 1
                    });
                } else {
                    app.to.update({
                        velocity: 0,
                        position: app.to.pos
                    });
                }
            } else if (evt.keyCode == 37) {
                app.to.update({
                    position: app.to.pos - delta
                });
            } else if (evt.keyCode == 39) {
                app.to.update({
                    position: app.to.pos + delta
                });
            } else if (evt.key.toLowerCase() == "f") {
                API.toggle_fullscreen();
            } else if (evt.key.toLowerCase() == "s") {
                toggle_sound();
            }
        });
    }

    // Load webvtt subtitles
    API.load_subs = function(sequencer, url, params) {

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
                    for (var i = 0; i < lines.length; i++) {
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

    // Load json subtitles (start, end, text) + any other data
    API.load_json_subs = function(sequencer, url, params) {
        let idx = 0;
        fetch(url)
            .then(response => response.json())
            .then(data => {
                data.forEach(sub => {
                    let id = "sub" + idx;
                    idx++;
                    API.subsequencer.addCue(id, [sub.start, sub.end], sub);
                });
            });
    };

    // ************ Render advanced subs - chat style *************
    API._render_advanced_sub = function(data, targetElement) {
        console.log("RENDER_SUB", data);
        let message = data.data;
        if (!message.text) return;

        let _make_msg = function(who, text, data) {
            if (!text) throw new Error("Refusing to make message with no text");

            text = text.replaceAll("-<br>", " ").replaceAll("<br>", " ");

            console.log("_make_msg", who, text, data, API.cast[who]);

            if (who == "info" || who == "scene") {
              console.log("INFO thing", API.options.tts);
                if (API.options.tts) {
                  API.speak(text, data.voice || 0);
                }
                return;
            }
            /*
            if (who == "scene") { // || who == "info") {
                // This is a bit of information, so it's in a different spot
                API.targetElement.querySelector(".infobox").innerHTML = text;
                API.targetElement.querySelector(".infobox").classList.remove("hidden");
                return;
            }
            */

            // It's a text - if we're still speaking, pause the video
            if (API.options.tts && API.options.tts_autopause && _is_speaking) {
                app.to.update({
                    velocity: 0
                });
                __autopaused = true;
            } else {
              console.log("Not pausing", API.options.tts, API.options.tts_autopause, _is_speaking);
            }

            let template = document.querySelector("template#message").content.cloneNode(true);
            let msg = template.querySelector("div");
            msg.setAttribute("id", data.key);
            if (API.cast[who] === undefined) who = "undefined";
            if (text) {
                if (API.cast[who]) {
                    msg.style.background = API.cast[who].color || "lightgray";
                    msg.querySelector(".icon").src = API.cast[who].src
                } else {
                    msg.querySelector(".icon").src = "undefined.png";
                }
            } else {
                console.log("Hide icon");
                msg.querySelector(".icon").classList.add("hidden");
            }
            // If we have an index - we know there are multiple on screen
            if (data.idx != undefined) {
                console.log("Got index");                
                if (data.idx % 2 == 1) msg.classList.add("lower")
                else msg.classList.add("higher");
            } else {
              // Detect if there is another one on screen already
              if (targetElement.querySelectorAll(".advancedsub").length > 0) {
                console.log("Going hi and lo (auto)", targetElement, );
                targetElement.querySelector(".advancedsub").classList.add("higher");
                msg.classList.add("lower");
              }

            }

            if (text.startsWith("- ")) text = text.substr(2);
            msg.querySelector(".text").innerHTML = text || "";
            // If right aligned, fix that
            if (data.data.align == "right") {
                console.log("Right align");
                msg.classList.add("right");
            }

            // TODO? Trick for a double-sub - the second part is a bit later, so delay it?
            if (data.idx % 2 == 1) {
                let original = msg.style.display;
                msg.style.display = "none";
                setTimeout(function() {
                    msg.style.display = original
                }, 700 * data.idx);
            }
            console.log("woop");
            return msg;
        }

        if (Array.isArray(message.who)) {
            // The sub has multiple messages within them, assume <br> or "- " is the limiter in the text
            let lines = message.text.split("<br>");
            for (let idx = 0; idx < message.who.length; idx++) {
                data.idx = idx;
                let msg = _make_msg(message.who[idx], lines[idx], data);
                if (msg) targetElement.appendChild(msg);
            }
        } else {
            let msg = _make_msg(message.who, message.text, data);
            if (msg) targetElement.appendChild(msg);
        }
    };


  API.sequencer.on("change", function(evt) {

    let align = function(element, align) {
      if (!element) return;
      if (align === "right") {
        element.classList.add("rightalign")
      } else {
        element.classList.remove("rightalign")
      }
    };

    let itm = evt.new.data;
    if (itm.pos) {
      console.log("Position", itm.pos);
      if (!itm.target) itm.target = ".maincontent";
      let target = API.targetElement.querySelector(itm.target);
      target.pos = itm.pos;
      API.targetElement.pos = itm.pos;
      target.animate = itm.animate;
      API.targetElement.animate = itm.animate;
      //console.log("Will resize", target.parentElement, target);
      //API.resize(target.parentElement);
      API.resize();
      API.resize(target);
      /*
      setTimeout(function() {
        console.log("RESIZE");
        API.resize();
      }, 0);
      */
    }

    if (itm.text) {
      align(API.set_subtitle(itm.text), itm.align);
    }

    if (itm.overlay) {
      align(API.set_overlay(itm.overlay), itm.align);
    }

    console.log("itm", itm);
    if (itm.emotion) {
      console.log("Loading emotion", itm, evt.new.key)
      let e = API.targetElement.querySelector(".emotion");
      e.src = itm.url;
      e.key = evt.new.key;
      e.classList.remove("hidden");
      console.log("e", e.key, e);
    }

    /*
    if (API.options.markingbox) {
      let box = API.targetElement.querySelector(".markingbox");
      box.style.left = itm.pos[0] + "%";
      box.style.top = itm.pos[1] + "%";
    }
*/
  });


  API.sequencer.on("remove", function(evt) {
    let itm = evt.old.data;
    if (itm.text) {
      API.set_subtitle("");;
    }
    if (itm.overlay) {
      API.set_overlay();
    }
    if (itm.emotion) {
      let e = API.targetElement.querySelector(".emotion");
      if (e.key == evt.old.key) {
        e.classList.add("hidden");
      }
    }
  });



    return API;
}