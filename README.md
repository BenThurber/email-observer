# email-observer
Listens to an email server and triggers a callback when a new email message is received.  Adapted from [Elijas/email-notifier](https://github.com/Elijas/email-notifier).

## 1. Business value
Polling a mailbox with IMAP is slow and taxing on the email server.  This package uses IMAP IDLE which allows the server to efficiently push new emails to the client without polling.

This package abstracts away the complexities of IMAP IDLE and provides a simple interface to trigger a callback when a new email is received.

## 2. Development status 
Early prototype. Further development: Needs unit tests.

## 3. Usage

### 3.1. Installation
```bash
pip install .
```

### 3.2. Basic Usage

An [observer pattern](https://en.wikipedia.org/wiki/Observer_pattern) is used for processing incoming emails.  To receive email events, a class must implement the on_mail_received method of the AbstractEmailObserver class.  This callback is triggered when one or more new messages arrive, or are moved to the mailbox.

Each new message is an `email.message.Message` object from the built-in [email](https://docs.python.org/3/library/email.html) module.

```python
from emailobserver import EmailNotifier, AbstractEmailObserver
from email.message import Message

class EmailObserver(AbstractEmailObserver):
    def on_mail_received(self, new_messages: list[Message]):
        print(len(new_messages), "New messages received.")

observer = EmailObserver()

notifier = EmailNotifier('imap.someserver.com', 'someuser@someserver.com', 'password')
notifier.register_observer(observer)
notifier.start()
```

### 3.3. Authentication

Authentication with a mail server requires a **mail server address**, **username**, and **password**.  These can be provided in three ways:

1. By setting the environment variables `EMAIL_OBSERVER_IMAP_SERVER`, `EMAIL_OBSERVER_USER`, and `EMAIL_OBSERVER_PASSWORD`.

2. Directly in the `EmailNotifier` constructor:

```python
from emailobserver import EmailNotifier

notifier = EmailNotifier('imap.someserver.com', 'someuser@someserver.com', 'password')
```

3. Or by specifying custom names for environment variables:

```python
from emailobserver import EmailNotifier

notifier = EmailNotifier(imap_server_env='EMAIL_OBSERVER_IMAP_SERVER',
                         env_username='EMAIL_OBSERVER_USER',
                         env_password='EMAIL_OBSERVER_PASSWORD')
```

### 3.4. Saving State Between Sessions

To track new emails across sessions, the `UIDNEXT` and `UIDVALIDITY` parameters can be stored on disk.  This can be achieved by overriding the `load_state` and `save_state` methods of `EmailNotifier`.

```python
from emailobserver import EmailNotifier
import json

class CustomEmailNotifier(EmailNotifier):
    def load_state(self) -> dict:
        try:
            with open('state.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def save_state(self, state: dict):
        with open('state.json', 'w') as f:
            json.dump(state, f)
```

When `CustomEmailNotifier` starts, it will first fetch all new messages received since the previous session.

#### Acknowledgements and sources
- https://github.com/Elijas/email-notifier
- https://gist.github.com/jexhson/3496039/
- https://stackoverflow.com/a/31464349/1544154
