from flask import Flask, render_template, Response, request, jsonify
import queue
import json
from utils import format

class Broadcaster:
    def __init__(self):
        self.subscriptions = []

    def subscribe(self):
        """Return a blocking message queue to a client"""
        msg_queue = queue.Queue(maxsize=3)
        self.subscriptions.append(msg_queue)
        return msg_queue
    
    def broadcast_sse(self, msg):
        """Broadcast a message to all subscribing clients."""
        sse_msg = format.format_sse(data=json.dumps(msg))

        for i in reversed(range(len(self.subscriptions))):
            try:
                self.subscriptions[i].put_nowait(sse_msg)
            # Remove clients who are not consuming messages
            except queue.Full:
                del self.subscriptions[i]

app = Flask(__name__)
broadcaster = Broadcaster()

@app.route("/", methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        data = request.json
        broadcaster.broadcast_sse(data)
        return jsonify({"Status": "OK"})
    else:
        return render_template('index.html')

@app.route('/subscribe', methods=['GET'])
def subscribe():
    """Subscribe to messages from the broadcaster."""
    def stream():
        msg_queue = broadcaster.subscribe()
        while True:
            # Block until a new message arrives
            sse_msg = msg_queue.get()
            yield sse_msg

    return Response(stream(), mimetype='text/event-stream')
