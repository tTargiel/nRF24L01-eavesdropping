import eventlet
eventlet.monkey_patch()

from core.state_machine import StateMachine
from flask_socketio import SocketIO
from flask import Flask, render_template


app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
machine = StateMachine(app, socketio)


@app.route('/')
def index():
    return render_template('index.html')


@socketio.on('idle')
def idle():
    machine.idle_state()


@socketio.on('listen')
def listen():
    machine.listening_state()


@socketio.on('sniff')
def sniff():
    machine.sniffing_state()


@socketio.on('abort')
def abort():
    machine.aborting_state()


@socketio.on('PA_MIN')
def pa_min():
    machine.power = 0


@socketio.on('PA_LOW')
def pa_low():
    machine.power = 1


@socketio.on('PA_HIGH')
def pa_high():
    machine.power = 2


@socketio.on('PA_MAX')
def pa_max():
    machine.power = 3


if __name__ == '__main__':
    # Use eventlet's WSGI server instead of the built-in Flask server
    eventlet.wsgi.server(eventlet.listen(('', 5000)), app)
