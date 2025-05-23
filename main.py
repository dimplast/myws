
import secrets
from fasthtml.common import *


# Tailwind CSS κλάσεις ως μεταβλητές
container_cls = "max-w-2xl mx-auto p-4"
login_form_cls = "flex flex-col gap-4 p-6 bg-gray-100 rounded-lg shadow-md"
login_input_cls = "p-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
login_button_cls = "bg-blue-500 text-white p-2 rounded hover:bg-blue-600 transition"

chat_form_cls = "flex items-center gap-2 mt-4"
chat_input_cls = "flex-1 p-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
chat_button_cls = "bg-blue-500 text-white p-2 rounded hover:bg-blue-600 transition"
error_cls = "text-red-600 bg-red-100 p-4 rounded border border-red-300 flex items-center gap-2"
join_cls = "text-green-600 italic text-sm"
leave_cls = "text-red-600 italic text-sm"
session_debug_cls = "text-sm text-gray-600 bg-gray-50 p-2 rounded border border-gray-200"

msg_list_cls = "h-96 overflow-y-auto p-4 rounded bg-gray-50 flex flex-col gap-3 scroll-smooth"

user_msg_cls = "ml-auto bg-blue-100 text-blue-900 p-3 rounded-lg max-w-xs shadow-sm mb-2 flex justify-end"
other_msg_cls = "mr-auto bg-gray-200 text-gray-900 p-3 rounded-lg max-w-xs shadow-sm mb-2"

hdrs = (
    Link(rel="stylesheet", href="output.css", type="text/css"),
    Script(''' 
    
    document.addEventListener('htmx:wsConnecting', function() {
        console.log('Η σύνδεση WebSocket ξεκινά');
    });
           
    document.addEventListener('htmx:wsAfterMessage', function(evt) {
            console.log('WebSocket connection opened');
            const container = document.getElementById('msg-list');
            container.scrollTop = container.scrollHeight;
    });   
    ''')
)

app = FastHTML(exts='ws', secret_key='soopersecret', hdrs=hdrs)
rt = app.route

@rt("/{fname:path}.{ext:static}")
def get(fname:str, ext:str): 
    return FileResponse(f'{fname}.{ext}')

db = database('chat.db')

# Δημιουργία πινάκων για χρήστες και μηνύματα
users = db.t.users
if users not in db.t:
    users.create(
        id=int, username=str, session_id=str, ws_id=str, pk='id'
    )

messages = db.t.messages
if messages not in db.t:
    messages.create(
        id=int, username=str, message=str, pk='id'
    )

ws_clients = {}

# Βοηθητική συνάρτηση για ασφαλή ανάκτηση εγγραφής με get
def safe_get(table, pk_value):
    try:
        return table.get(pk_value)
    except NotFoundError:
        return None

# Συνάρτηση για καθαρισμό συνεδρίας
def clear_session(sess):
    sess.pop('user_id', None)
    sess.pop('username', None)
    sess.pop('session_id', None)


# Συνάρτηση που δημιουργεί το πεδίο εισαγωγής για το chat
def mk_inp(): return Input(id='msg', autofocus=True, placeholder="Type your message", cls=chat_input_cls)

def ChatMessage(msg, sess, cl=None):
    return Li(f"{msg[0]} : {msg[1]}", cls=user_msg_cls if msg[0] == sess['username'] else other_msg_cls)
    pass

# Φόρμα σύνδεσης
@rt('/login')
def get():
    return Titled("Login to Chat",
        Div(    
            Form(
                Label("Username", Input(id='username', name='username', required=True, cls=login_input_cls)),
                Button("Join Chat", type="submit", cls=login_button_cls),
                action='/set_username', method='post',
                cls=login_form_cls
            )
        ), id='container', cls=container_cls,  
    )

# Αποθήκευση ονόματος χρήστη στη session και ανακατεύθυνση στο chat
@rt('/set_username')
def post(username: str, sess):
    sess['username'] = username  # Αποθήκευση ονόματος στη session
    if 'session_id' not in sess:
        sess['session_id'] = secrets.token_hex(16)
    user = users.insert(username=username, session_id=sess['session_id'])
    sess['user_id'] = user['id']
    return RedirectResponse('/', status_code=303)

# Αρχική σελίδα (chat)
@rt('/')
def home(sess):
    username = sess.get('username', None)
    if not username:  # Αν δεν υπάρχει όνομα, ανακατεύθυνση στη σελίδα login
        return RedirectResponse('/login', status_code=303)
    
    msg_list = messages()
    return Titled(f"Chat as {username}",
        Div(
            Ul(*[ChatMessage((m['username'], m['message']), sess) for m in msg_list], id='msg-list', cls=msg_list_cls),  # Εμφάνιση ονόματος και μηνύματος
            Form(mk_inp(), id='form', ws_send=True, hx_ext='ws', ws_connect='/ws', cls=chat_form_cls),  # Φόρμα για αποστολή μηνυμάτων
            Div(f"Session data: {dict(sess)}", cls=session_debug_cls),  # Debugging
            Div(f'Messages: {len(msg_list)}', cls=session_debug_cls),  # Αριθμός μηνυμάτων
            Div(f'Connected users: {len(ws_clients)}', cls=session_debug_cls),  # Αριθμός συνδεδεμένων χρηστών
            Div(f'Messages: {(msg_list)}', cls=session_debug_cls),  # Αριθμός μηνυμάτων
            id='container', cls=container_cls
        ))

# Χειρισμός σύνδεσης (async για να υποστηρίζει await)
async def on_connect(ws, send, sess):
   
    username = sess.get('username', 'Anonymous')
    ws_id = str(id(ws))
    ws_clients[ws_id] = send
    if 'session_id' not in sess:
        sess['session_id'] = secrets.token_hex(16)
    if 'user_id' in sess:
        # Χρήση safe_get αντί για users.get για να χειριστεί NotFoundError
        if safe_get(users, sess['user_id']):
            users.update(dict(ws_id=ws_id), id=sess['user_id'])
            for client_id, send_fn in list(ws_clients.items()):
                try:
                    pass
                except Exception as e:
                    ws_clients.pop(client_id, None)  # Αφαίρεση αποσυνδεδεμένου πελάτη
        else:
            clear_session(sess)
  

# Χειρισμός αποσύνδεσης (async για να υποστηρίζει await)
async def on_disconnect(ws, sess):
  
    ws_id = str(id(ws))
    user = first(users.rows_where('ws_id = ?', [ws_id]))
    # Αφαίρεση πελάτη από ws_clients πριν την αποστολή ειδοποιήσεων
    ws_clients.pop(ws_id, None)
    if user:
        for client_id, send_fn in list(ws_clients.items()):
            try:
                pass
            except Exception as e:
                ws_clients.pop(client_id, None)  # Αφαίρεση αποσυνδεδεμένου πελάτη
    # Χρήση safe_get αντί για users.get για να χειριστεί NotFoundError
    if 'user_id' in sess and safe_get(users, sess['user_id']):
        users.update(dict(ws_id=None), id=sess['user_id'])

# Χειρισμός μηνυμάτων WebSocket
@app.ws('/ws', conn=on_connect, disconn=on_disconnect)
async def ws(msg: str, send, sess):
    username = sess.get('username', 'Anonymous')  # Λήψη ονόματος από τη session
    # Προσθήκη του μηνύματος με το όνομα στη λίστα
    messages.insert(username=username, message=msg)

    for client_id, send_fn in list(ws_clients.items()):
        client_user = first(users.rows_where('ws_id = ?', [client_id]))
        client_username = client_user['username'] if client_user else None
        new_msg = (client_username, msg)
        # Ενημέρωση όλων των συνδεδεμένων χρηστών
        new_message = ChatMessage(new_msg, sess, client_username) 
        await send_fn(Div(new_message,hx_swap_oob='beforeend', id='msg-list'))  # Αποστολή της ενημερωμένης λίστας
    # Επιστροφή νέου πεδίου εισαγωγής για τον αποστολέα
    return mk_inp()

# Εκκίνηση του server
serve(port=5001)    
