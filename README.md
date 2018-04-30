# email-notifier
Sends an Android notification immediately after new email (meeting certain criteria, by sender or subject) is received.

## Business value
Accounts added through POP3/IMAP to Gmail reroute their email with a ~<1h delay. This program solves the serious issue when immediate response is required in certain cases.

## Development status 
Stable early prototype. Further development: needs refactoring with tests, futhermore, POP3 interface is redundant (should only use IMAP).

## Tech Stack
- Python + IMAP, POP3
- Notifications managed by IFTTT
- Deployed on Heroku
