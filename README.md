# email-observer
Listens to an email mailbox and triggers a callback when a new email is received.  Adapted from [Elijas/email-notifier](https://github.com/Elijas/email-notifier).

## 1. Business value
Polling a mailbox with IMAP is slow and taxing on the email server.  This package uses IMAP IDLE which allows the server to efficiently push new emails to the client.  

This package abstracts away the complexities of IMAP IDLE and provides a simple interface to trigger a callback when a new email is received.

## 2. Development status 
Early prototype. Further development: needs refactoring with tests.

#### Acknowledgements and sources
- https://github.com/Elijas/email-notifier
- https://gist.github.com/jexhson/3496039/
- https://stackoverflow.com/a/31464349/1544154
