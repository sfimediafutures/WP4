let subCloud = function(dst, url, sequencer, options, chart_options) {

    return new Promise(function(resolve, reject) {

        let API = {sequencer: sequencer};

        options = options || {};
        options.maxWords = options.maxWords || 50;
        options.cutoff = options.cutoff | 0;
        chart_options = chart_options || {};

        let redraw_timer;
        let chart;


        let get_words = function(dataset, _options) {

            opt = _options || options;

            let list = [];
            let count = {};
            dataset.forEach(itm => {
                let text = itm.data.text || itm.data;
                // text += " " + itm.data.who; 
                // Should use stoplist
                text = text.toLowerCase().replaceAll(/<[^>]+>/g, " ");
                text.replace(/[.,\/#!$%\^&\*;:\?{}=\-_`~()]/g,"", "").replaceAll("\n", " ").split(" ").forEach(word => {

                    if (word.trim().length <= 2) return;

                    if (API.stoplist.indexOf(word.toLowerCase()) > -1) return;

                    if (!count[word]) {
                        count[word] = 1;
                    } else {
                        count[word]++;
                    }
                });
            });


            for (let k in count) {
                if (opt.cutoff && count[k] < opt.cutoff) continue;
                list.push({name: k, weight: count[k]});
            }

            list.sort((el1, el2) => el2.weight - el1.weight);
            list = list.slice(0, opt.maxWords);
            return list;
        }

        API.get_words_by_times = function(start, end, _options) {
            let dataset = [];
            sequencer.getCues().forEach(item => {
                let cue = item.data;
                if (cue.who == "info") return;
                if (cue.start < end && cue.end > start) {
                    dataset.push(item);
                }
            });

            return get_words(dataset, _options);
        }

        API.plot_chart_by_times = function(dst, start, end, _options) {
            let dataset = [];
            sequencer.getCues().forEach(cue => {
                if (cue.data.start < end && cue.data.end > start) {
                    dataset.push(cue);
                }
            });

            console.log("Plotting data from", start, "to", end);
            return API.plot_chart(dst, dataset, _options);
        }

        API.plot_chart = function(dst, dataset, _options) {
            let o = options;
            for (let key in _options) {
                o[key] = _options[key];
            }

            let list = get_words(dataset, o);
            return create_chart(dst, list, o);
        }


        let create_chart = function(dst, list, options) {
            console.log("OPTIONS", options, "words", list);
            let o = options;
            o.series = [{
                type: 'wordcloud',
                data: list
              }];

            if (chart_options.rotation) o.series[0].rotation = chart_options.rotation;
            chart = Highcharts.chart(dst, o);
            return chart;
        }

        API.redraw = function(full_set, _full_options) {
            //
            if (redraw_timer) {
                clearTimeout(redraw_timer);
                redraw_timer = undefined;
                return;
            }

            redraw_timer = setTimeout(() => {
                console.log("Creating wordlist");
                let set;
                if (full_set) {
                    set = API.sequencer.getCues();
                    options = _full_options || options;
                } else {
                    set = API.sequencer.getActiveCues();
                }
                let list = get_words(set, options);
                if (list.length > -1) {
                    console.log("Drawing to", dst, list.length, "words");

                    if (!chart) {
                        chart = create_chart(dst, list, options);
                    } else {
                        console.log("Updating", dst, list);
                        chart.series[0].setData(list);
                        chart.redraw();
                    }

                    // API.wordcloud = WordCloud(dst, {list: list, fconfig:config});
                }
                redraw_timer = undefined;
            }, 10);

        }

        API.sequencer.on("change", function(evt) {
            return API.redraw();
        });

        API.sequencer.on("remove", function(evt) {
            return API.redraw();
        });

        let f = fetch("lib/stoplist_combined.json").then(e => e.json()).then(data => API.stoplist = data);

        if (!url) {
            f.then(() => resolve(API));
            return;
        }

        fetch(url)
        .then(e => e.json())
        .then(manifest => {
            if (manifest.subtitles) {
                let suburl = manifest.subtitles[0].src;
                console.log("Loading subtitles from", suburl);
                if (suburl.endsWith(".json")) {
                    utils.loadJsonSubs(API.sequencer, suburl);
                } else if (suburl.endsWith(".vtt")) {
                    utils.loadVtt(API.sequencer, suburl);
                }
            }

            resolve(API);
        });
    });
 }
