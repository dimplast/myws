from fasthtml.common import *

# Δημιουργία εφαρμογής FastHTML με ενεργοποιημένη την επέκταση WebSocket και session


app = FastHTML(exts='ws', secret_key='soopersecret')
rt = app.route

# Λίστα για αποθήκευση μηνυμάτων (τώρα κάθε μήνυμα είναι tuple: (όνομα, κείμενο))
msgs = []
# Λεξικό για αποθήκευση συνδεδεμένων χρηστών
users = {}

# Συνάρτηση που δημιουργεί το πεδίο εισαγωγής για το chat
def mk_inp(): return Input(id='msg', autofocus=True, placeholder="Type your message")

# Φόρμα σύνδεσης
@rt('/login')
def get():
    return Titled("Login to Chat",
        Form(
            Label("Username", Input(id='username', name='username', required=True)),
            Button("Join Chat", type="submit"),
            action='/set_username', method='post'
        ))

# Αποθήκευση ονόματος χρήστη στη session και ανακατεύθυνση στο chat
@rt('/set_username')
def post(username: str, sess):
    sess['username'] = username  # Αποθήκευση ονόματος στη session
    return RedirectResponse('/', status_code=303)

# Αρχική σελίδα (chat)
@rt('/')
def home(sess):
    username = sess.get('username', None)
    if not username:  # Αν δεν υπάρχει όνομα, ανακατεύθυνση στη σελίδα login
        return RedirectResponse('/login', status_code=303)
    return Titled(f"Chat as {username}",
        Div(
            Ul(*[Li(f"{name}: {msg}") for name, msg in msgs], id='msg-list'),  # Εμφάνιση ονόματος και μηνύματος
            Form(mk_inp(), id='form', ws_send=True),  # Φόρμα για αποστολή μηνυμάτων
            hx_ext='ws', ws_connect='/ws'
        ))

# Χειρισμός σύνδεσης και αποσύνδεσης
def on_connect(ws, send, sess):
    username = sess.get('username', 'Anonymous')  # Λήψη ονόματος από τη session
    users[str(id(ws))] = (send, username)  # Αποθήκευση send και username
    print(f"User {username} connected")

def on_disconnect(ws):
    user_id = str(id(ws))
    username = users.get(user_id, (None, 'Anonymous'))[1]
    users.pop(user_id, None)
    print(f"User {username} disconnected")

# Χειρισμός μηνυμάτων WebSocket
@app.ws('/ws', conn=on_connect, disconn=on_disconnect)
async def ws(msg: str, send, sess):
    username = sess.get('username', 'Anonymous')  # Λήψη ονόματος από τη session
    # Προσθήκη του μηνύματος με το όνομα στη λίστα
    msgs.append((username, msg))
    # Ενημέρωση όλων των συνδεδεμένων χρηστών
    updated_list = Ul(*[Li(f"{name}: {msg}") for name, msg in msgs], id='msg-list')
    for u, _ in users.values():
        await u(updated_list)  # Αποστολή της ενημερωμένης λίστας
    # Επιστροφή νέου πεδίου εισαγωγής για τον αποστολέα
    return mk_inp()

# Εκκίνηση του server
serve()
