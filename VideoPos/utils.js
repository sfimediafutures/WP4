
function _utils() {
    let API = {};


    API.secondsToString = function(seconds) {
        let s = "";
        if (seconds > 3600) {
            let h = Math.floor(seconds/3600);
            s += h + "h "
            seconds -= 3600 * h;
        }
        if (seconds > 60) {
            let m = Math.floor(seconds/60)
            s += m + "m "
            seconds -= 60 * m
        }

        s += seconds.toFixed(0) + "s"
        return s;
    }

    API.addWakeLock = function(timingObject) {
        let wakeLock = null;
        if ("wakeLock" in navigator) {

            // Function that attempts to request a screen wake lock.
            const requestWakeLock = async () => {
              try {
                wakeLock = await navigator.wakeLock.request();
                wakeLock.addEventListener('release', () => {
                  console.log('Screen Wake Lock released', wakeLock.released);
                });
                console.log('Screen Wake Lock released:', wakeLock.released);
              } catch (err) {
                console.error(`${err.name}, ${err.message}`);
              }
            };

            timingObject.on("change", evt => {
                if (timingObject.vel == 0) {
                    // Paused, release the lock
                    if (wakeLock) {
                        console.log("Releasing wake lock - paused");
                        wakeLock.release();
                        // wakeLock = null;
                    }
                } else {
                    console.log("Requesting wake lock");
                    requestWakeLock();
                }
            });
        }
    }

    API.getParameterByName = function(name) {
        name = name.replace(/[\[]/, "\\\[").replace(/[\]]/, "\\\]");
        var regex = new RegExp("[\\?&]" + name + "=([^&#]*)"),
              results = regex.exec(location.search);
        return results == null ? "" : decodeURIComponent(results[1].replace(/\+/g, " "));
    }


    API.loadVtt = function(sequencer, url, params) {

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
                    setTimeout(resolve, 1);
                }).catch(err => reject(err));
        });
    };

    API.loadJsonSubs = function(sequencer, url, params) {
        return new Promise(function(resolve, reject) {
            let idx = 0;
            let p = fetch(url);
            p.then(response => response.json())
                .then(data => {
                    console.log("Adding data", data.length)
                    data.forEach(sub => {
                        let id = "sub" + idx;
                        idx++;
                        if (sub.who) sub.who = String(sub.who);
                        sequencer.addCue(id, new TIMINGSRC.Interval(sub.start, sub.end), sub);
                    });
                    console.log("Resolving", sequencer.getCues().length)
                    setTimeout(resolve, 1);
                });
        });
    };


    return API;
}


var utils = _utils();
