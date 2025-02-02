# email-observer
Listens to an email mailbox and triggers a callback when a new email is received.  Adapted from [Elijas/email-notifier](https://github.com/Elijas/email-notifier).

## 1. Business value
Polling a mailbox with IMAP is slow and taxing on the email server.  This package uses IMAP IDLE which allows the server to efficiently push new emails to the client.  

This package abstracts away the complexities of IMAP IDLE and provides a simple interface to trigger a callback when a new email is received.

## 2. Development status 
Early prototype. Further development: needs refactoring with tests.

## 3. Usage

### 3.1. Installation
```bash
pip install emailobserver
```

### 3.2. Basic Usage

An [observer pattern](https://en.wikipedia.org/wiki/Observer_pattern) is used for processing incoming emails.  To receive email events, a class must implement the on_mail_received method of the EmailObserver class.

```python
from emailobserver import EmailNotifier, EmailObserver

class Observer(EmailObserver):
    def on_mail_received(self, new_messages: list, all_messages: list):
        print("Message received!")

observer = Observer()

notifier = EmailNotifier('imap.gmail.com', 'someuser@gmail.com', 'password')
notifier.register_observer(observer)
notifier.start()
```

### 3.3. Authentication

Authentication with a mail server requires a **mail server address**, **username**, and **password**.  These can be provided in three ways:

1. By setting the environment variables `EMAIL_OBSERVER_IMAP_SERVER`, `EMAIL_OBSERVER_USER`, and `EMAIL_OBSERVER_PASSWORD`.

2. Directly in the `EmailNotifier` constructor:

```python
from emailobserver import EmailNotifier

notifier = EmailNotifier('imap.gmail.com', 'someuser@gmail.com', 'password')
```

3. Or by specifying custom names for environment variables:

```python
from emailobserver import EmailNotifier

notifier = EmailNotifier(imap_server_env='EMAIL_OBSERVER_IMAP_SERVER', env_username='EMAIL_OBSERVER_USER',
                         env_password='EMAIL_OBSERVER_PASSWORD')
```


#### Acknowledgements and sources
- https://github.com/Elijas/email-notifier
- https://gist.github.com/jexhson/3496039/
- https://stackoverflow.com/a/31464349/1544154
