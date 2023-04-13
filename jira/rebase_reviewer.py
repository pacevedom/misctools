from github import Github
import os
import logging


REBASE_AUTHOR = 'microshift-rebase-script[bot]'
MANDATORY_LABELS = ['approved', 'lgtm']
MANDATORY_LABELS_BACKPORT = MANDATORY_LABELS + ['backport-risk-assessed', 'bugzilla/valid-bug', 'cherry-pick-approved']
BACKPORT_REFS = ['release-4.13', 'release-4.12']
RETITLE_COMMAND = '/retitle'
LABEL_COMMAND = '/label'

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

def analyze_commit_status(statuses):
    contexts = set([status.context for status in statuses])
    for context in contexts:
        if context == 'tide':
            continue
        states = list(filter(lambda x: x.context == context, statuses))
        if states[0].state != 'success':
            return False
    return True

def pr_tests_passed(pr):
    last_commit = [commit for commit in pr.get_commits()][-1]
    return analyze_commit_status(last_commit.get_statuses())

def is_held(pr):
    pr_labels = pr.get_labels()
    for label in pr_labels:
        if label.name == 'do-not-merge/hold':
            return True
    return False

def get_missing_labels(pr):
    mandatory_labels = MANDATORY_LABELS
    missing_labels = set(MANDATORY_LABELS)
    if pr.base.ref in BACKPORT_REFS:
        mandatory_labels = MANDATORY_LABELS_BACKPORT
        missing_labels = set(MANDATORY_LABELS_BACKPORT)
    pr_labels = pr.get_labels()
    for label in pr_labels:
        if label.name in mandatory_labels:
            missing_labels.remove(label.name)
    return list(missing_labels)

def needs_retitle(title):
    return not title.startswith('NO-ISSUE')

def add_comment(pr, comment):
    pr.create_issue_comment(comment)

def build_comment_labels(labels):
    comment = ''
    for label in labels:
        if label == 'lgtm':
            comment += '/lgtm\n'
        elif label == 'approved':
            comment += '/approve\n'
        else:
            comment += f'{LABEL_COMMAND} {label}\n'
    return comment

def main():
    token = os.getenv('GITHUB_TOKEN')
    g = Github(token)
    repo = g.get_repo('openshift/microshift')
    pulls = repo.get_pulls(state='open')
    for pull in pulls:
        if pull.user.login != REBASE_AUTHOR:
            continue
        logging.info(f'Checking PR {pull.number}>{pull.title}')
        if needs_retitle(pull.title):
            comment = f'{RETITLE_COMMAND} NO-ISSUE:{pull.title}'
            logging.info('Retitle required')
            add_comment(pull, comment)

        if is_held(pull):
            logging.info('Hold label found. Skipping')
            continue

        if not pr_tests_passed(pull):
            logging.info('Tests not passed yet. Skipping')
            continue

        missing_labels = get_missing_labels(pull)
        if len(missing_labels) == 0:
            logging.info('No missing labels. Skipping')
            continue

        comment = build_comment_labels(missing_labels)
        logging.info(f'Required labels missing: {missing_labels}')
        add_comment(pull, comment)

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        logging.exception('Exception occurred')
