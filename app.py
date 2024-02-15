from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from core.state_machine import StateMachine

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
machine = StateMachine()

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('idle')
def idle():
    machine.idle_state()
    emit('state', {'state': machine.state}, broadcast=True)

@socketio.on('sniff')
def sniff():
    machine.sniffing_state()
    emit('state', {'state': machine.state}, broadcast=True)

@socketio.on('listen')
def listen():
    machine.listening_state()
    emit('state', {'state': machine.state}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='localhost', port=5000)