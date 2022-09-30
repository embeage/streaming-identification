var evtSource = new EventSource('http://127.0.0.1:5000/subscribe');

var streams = [];

const RED = '#FF0000';
const GREEN = '#39ce00';
const TIMESTAMP = 6;
const VIDEOLENGTH = 2;
const MAX_SEGMENTS = 15;
const UNIT = 1000;
const UNIT_STRING = 'kB';
const FACTOR = 5;
const YSCALE = UNIT*FACTOR
const TABLE_COLUMNS = 7;
const BUFFER_SECONDS = 60;

evtSource.onmessage = async function(e) {
    analyze(e.data);
}

function analyze(json_data) {

    const data = JSON.parse(json_data);
    const src = data["IP src"];
    const dst = data["IP dst"];
    const captured_segment = data["Captured segment"];
    const match = data["Match"];
    const match2 = data["Match2"];
    const match3 = data["Match3"];
    const best_title = data["Best match"];
    const proba = data["Probability"];
    
    let cid = idHash(src, dst);
    let stream = streams.find(({cid : n}) => n == cid);
    if(!stream) {
        console.info(`%cNew stream: ${src} -> ${dst}, CID: ${cid}.`, 
                    'color:blue; font:15px bold');
        stream = createAnalysis(cid, src, dst);
    }
    updateGraph(stream, captured_segment, match, proba);
    updateTable(stream, match, match2, match3, best_title, proba);
    updateVideo(stream, match);
}

function updateVideo(stream, match) {

    const cid = stream['cid'];
    const playing = stream['playing'];
    let player = stream['player'];
    
    if((match.length == 0) && playing){
        console.info(`%cIdentification lost. CID: ${cid}`, 
                    'color:Red; font:15px bold');
        stream['player'].pause();
        stream['playing'] = false;
    } else if((match.length != 0) && (!playing || player.isPaused())) {
        console.info(`%cIdentification succeeded. CID: ${cid}`,
                    'color:LimeGreen; font:15px bold');
        const svt_id = match[2];
        const tstamp = match[5];

        // Initialization needs a manifest URL
        fetchManifest(svt_id).then(manifest => {
            if(!stream['initialized']) {
                player = initPlayer(cid, manifest, tstamp);
                stream['player'] = player;
                stream['initialized'] = true;
            } else
                updatePlayer(cid, stream['player'], manifest, tstamp);
        });
        stream['playing'] = true;
    }
}

function updateGraph(stream, data, match, proba) {

    let graph = stream['graph'];

    // Avoid bars overflowing on the Y-axis
    data = parseInt(data)/UNIT;
    if(data > (YSCALE - (UNIT/2)))
        data = YSCALE - (UNIT/2);

    graph.data = graph.data.concat(data);

    // Shift out segments in the graph like a FIFO queue
    if(graph.data.length > MAX_SEGMENTS)
        graph.data = RGraph.arrayShift(graph.data);

    (proba > 75) ? graph.set('colors', [GREEN]) : graph.set('colors', [RED]);

    RGraph.redraw();
}

function updateTable(stream, match, match2, match3, best_title, proba) {

    let table = stream['table'];

    let old_tbody = table.querySelector('tbody');
    let old_thead = table.querySelector('thead.video-type');
    let new_tbody = document.createElement('tbody');
    let new_thead = document.createElement('thead');
    new_thead.classList.add('video-type');

    if(proba > 75) {
        new_thead.append(setTableHead('Identification succeeded: ' + proba + '%'));
        new_tbody.append(setTableRows(match));
        new_thead.classList.add('match');
    } else{
        new_thead.append(setTableHead('NaN'));
        new_tbody.append(setTableRows(match));
        new_tbody.append(setTableRows(match2));
        new_tbody.append(setTableRows(match3));
    }

    table.replaceChild(new_thead, old_thead);
    table.replaceChild(new_tbody, old_tbody);
}

function updatePlayer(cid, player, url, tstamp) {

    let video = document.querySelector('#videoplayer' + cid);
    url = url + '#t='+ tstamp.toString();

    player.reset();
    player.attachView(video);
    player.attachSource(url);
    player.setMute(true);
    player.setAutoPlay(true);

    player.updateSettings({
        streaming: {
            buffer: {
                stableBufferTime: BUFFER_SECONDS,
                bufferTimeAtTopQuality: BUFFER_SECONDS
            }
        }
    });
}

function createAnalysis(cid, src, dst) {
    
    let analysis = document.createElement('div');
    let graph_video = document.createElement('div');
    let table = document.createElement('div');
    
    analysis.classList.add('analysis');
    analysis.id = cid;
    graph_video.classList.add('graph-video-container');
    graph_video.id = 'graph-video-container' + cid;
    table.classList.add('table-container');
    table.id = 'table-container' + cid;

    analysis.appendChild(graph_video);
    analysis.appendChild(table);
    document.body.appendChild(analysis);
    
    let stream = {
        cid: cid,
        playing: false, 
        initialized: false, 
        graph: createGraph(cid, src, dst),
        table: createTable(cid), 
        player: null,
        matched: false
    };
    streams.push(stream);
    createVideoContainer(cid);
    
    return stream;
}

function createVideoContainer(cid) {

    let div = document.createElement('div');
    let vplayer = document.createElement('video');

    div.classList.add('videoplayer-container');
    vplayer.classList.add('videoplayer');
    vplayer.controls = true;
    vplayer.id = 'videoplayer' + cid;

    div.appendChild(vplayer);
    document.getElementById('graph-video-container' + cid).appendChild(div);

    return vplayer
}

function createGraph(cid, src, dst) {

    let canvas = document.createElement('canvas');
    
    canvas.id = 'cvs' + cid;
    canvas.width = '600';
    canvas.height = '250';
    canvas.textContent = '[No canvas support]';
    document.getElementById('graph-video-container' + cid).appendChild(canvas);

    // Initially set the x-axis to the correct length 
    let dummy_values = [];
    for (var i = 0; i < MAX_SEGMENTS; i++) {
        dummy_values.push(NaN)
    }
        
    var graph = new RGraph.Bar({
        id: canvas.id,
        data: dummy_values,
        options: {
            marginLeft: 75,
            backgroundGridVlines: false,
            title: `Source: ${src} - Destination: ${dst}`,
            titleSize: 12,
            titleBold: true,
            titledsVpos: 0.5,
            labelsAbove: true,
            labelsAboveAngle: 90,
            labelsAboveSize: 8,
            yaxisScaleMax: YSCALE,
            yaxisScaleUnitsPost: UNIT_STRING,
            xaxisTickmarksCount: MAX_SEGMENTS
        }
    });
    graph.draw();
    return graph;
}

function createTable(cid) {
    
    let table = document.createElement('table');
    let tbody = document.createElement('tbody');
    let status_thead = document.createElement('thead');
    let type_thead = document.createElement('thead');

    type_thead.classList.add('video-type');
    
    table.appendChild(type_thead);
    table.appendChild(status_thead);
    table.appendChild(tbody);
    table.id = 'table' + cid;

    // Header to display information about the video
    let row_0 = document.createElement('tr');
    let heading_0 = document.createElement('th');
    heading_0.innerHTML = 'NaN';
    heading_0.colSpan = TABLE_COLUMNS;
    row_0.appendChild(heading_0);
    type_thead.appendChild(row_0);

    let row_1 = document.createElement('tr');
    let heading_1 = document.createElement('th');
    heading_1.innerHTML = "Video";
    heading_1.classList.add('col1');
    let heading_2 = document.createElement('th');
    heading_2.innerHTML = "SVT id";
    let heading_3 = document.createElement('th');
    heading_3.innerHTML = "Bandwidth";
    let heading_4 = document.createElement('th');
    heading_4.innerHTML = "Quality";
    let heading_5 = document.createElement('th');
    heading_5.innerHTML = "Timestamp";
    let heading_6 = document.createElement('th');
    heading_6.innerHTML = "Probability";
    row_1.appendChild(heading_1);
    row_1.appendChild(heading_2);
    row_1.appendChild(heading_3);
    row_1.appendChild(heading_4);
    row_1.appendChild(heading_5);
    row_1.appendChild(heading_6);
    status_thead.appendChild(row_1);

    document.getElementById('table-container' + cid).appendChild(table);

    return table;
}

function setTableRows(video_info) {

    let row = document.createElement('tr');
    let column = 1;

    for(const piece of video_info) {
        if(column == VIDEOLENGTH){
            column++;
            continue;
        }

        let row_data = document.createElement('td');

        // Convert to HH:MM:SS
        if(column == TIMESTAMP)
            row_data.innerHTML = timestamp(piece);
        else
            row_data.innerHTML = piece;

        row_data.classList.add('column' + column);
        row.appendChild(row_data);
        column++;
    }
    return row;
}

function setTableHead(string) {

    let row = document.createElement('tr');
    let row_data = document.createElement('th');
    row_data.innerHTML = string;
    row_data.colSpan = TABLE_COLUMNS;
    row.appendChild(row_data);

    return row;
}

function initPlayer(cid, url, tstamp) {

    let player = dashjs.MediaPlayer().create();
    let container = document.querySelector('#videoplayer' + cid)

    url = url + '#t='+ tstamp.toString();
    player.initialize(container, url);
    player.setMute(true);
    player.setAutoPlay(true);

    // Configures the buffer according to the streaming service
    player.updateSettings({
        streaming: {
            buffer: {
                stableBufferTime: BUFFER_SECONDS,
                bufferTimeAtTopQuality: BUFFER_SECONDS
            }
        }
    });
    return player;
}

// Return the first viable svt manifest url
async function fetchManifest(svt_id) {

    let url = `https://api.svt.se/video/${svt_id}`;
    const response = await fetch(url);
    var metadata = await response.json();

    for (const video_ref of metadata['videoReferences']) {
        if(['dash-full', 'dash-avc', 'dash'].includes(video_ref['format'])){
            console.log(`SVT Play ID: ${svt_id}\nFetched manifest ${video_ref['url']}`)
            return video_ref['url']
        }
    }
}

// Converts seconds to timestamp
function timestamp(seconds) {

    var t = parseInt(seconds);
    return ('0' + Math.floor(t/3600) % 24).slice(-2) + ':' +
    ('0'+Math.floor(t/60)%60).slice(-2) + ':' + 
    ('0' + t % 60).slice(-2);
}

function idHash(src, dst) {

    const stream = src + dst
    var hash = 0;

    if (stream.length == 0) return hash;
    
    for (let i = 0 ; i < stream.length ; i++){
        var ch = stream.charCodeAt(i);
        hash = ((hash << 5) - hash) + ch;
        hash = hash & hash;
    }
    return hash;
}
