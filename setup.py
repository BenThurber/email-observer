from setuptools import setup, find_packages

setup(
    name='emailobserver',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'imaplib2',
    ],
    python_requires='>=3.11',
    url='https://github.com/EcotechServices/email-observer',
    author='Ben Thurber',
    author_email='ben@ecotechservices.co.nz, benjamin.thurber@protonmail.com',
    description='An easy to use observer that leverages IMAP with IDLE to monitor a mailbox in real time.',
)
