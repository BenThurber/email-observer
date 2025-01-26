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
```python
from emailobserver import EmailObserver

callback = lambda : print('New email received!')
observer = EmailObserver('imap.gmail.com', 'someuser@gmail.com', 'password')
observer.register_observer(callback)
observer.start()
```

### 3.3. Authentication

Authentication with a mail server requires a **mail server address**, **username**, and **password**.  These can be provided in three ways:

By setting the environment variables `EMAIL_OBSERVER_IMAP_SERVER`, `EMAIL_OBSERVER_USER`, and `EMAIL_OBSERVER_PASSWORD`.

Directly in the `EmailObserver` constructor:
```python
from emailobserver import EmailObserver
observer = EmailObserver('imap.gmail.com', 'someuser@gmail.com', 'password')
```

Or by specifying custom names for environment variables:
```python
from emailobserver import EmailObserver
observer = EmailObserver(imap_server_env='EMAIL_OBSERVER_IMAP_SERVER', env_username='EMAIL_OBSERVER_USER', env_password='EMAIL_OBSERVER_PASSWORD')
```


#### Acknowledgements and sources
- https://github.com/Elijas/email-notifier
- https://gist.github.com/jexhson/3496039/
- https://stackoverflow.com/a/31464349/1544154
