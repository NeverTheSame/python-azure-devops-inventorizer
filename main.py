import argparse
import base64
import json
import os
import re
import subprocess
import urllib.parse
from datetime import datetime, timezone

import requests
from requests.auth import HTTPBasicAuth

import colors_worker
from openai_worker import return_summary

continuation_token = 1
result_json = ""
current_batch_result_json = ""
batch_number = 0
has_more_results = False

def parse_args():
    """Parses command line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("project_name")
    parser.add_argument("wiki_name")
    parser.add_argument("code_wiki_name")
    parser.add_argument("ado_username")
    parser.add_argument("pat")
    parser.add_argument("number_of_items_for_most_visited_md", type=int,
                        help="number of items (x) in Most-visited-x-pages-in-last-y-days.md", default=10)
    parser.add_argument("number_of_days_for_most_visited_md", type=int,
                        help="number of days (y) in Most-visited-x-pages-in-last-y-days.md", default=30)

    parser.add_argument("do_new_articles", choices=["0", "1"])
    parser.add_argument("--number_of_days_for_new_articles_md", type=int,
                        help="number of days (y) in Articles-created-in-the-past-y-days.md", default=30,
                        required=False)

    return parser.parse_args()


def create_files_definitions(code_wiki_name, max_number_of_items_in_md_for_most_visited_pages,
                             number_of_days_for_new_articles_md, do_new_articles):
    """
    Generate file paths for various files used in the script.

    Args:
    code_wiki_name (str): The name of the wiki.
    max_number_of_items_in_md_for_most_visited_pages (int): The maximum number of items for most-visited pages.
    number_of_days_for_new_articles_md (int): The number of days for new articles.
    do_new_articles (str): A flag indicating whether to generate new articles.

    Returns:
    tuple: A tuple containing the following file paths:
        - local_git_repo_full_path (str): Full path to the local git repository folder.
        - most_visited_json_full_path (str): Full path to the JSON file for most-visited pages.
        - most_visited_md_full_path (str): Full path to the Markdown file for most-visited pages.
        - new_articles_txt_full_path (str): Full path to the text file for new articles (if do_new_articles is "1").
        - new_articles_md_full_path (str): Full path to the Markdown file for new articles (if do_new_articles is "1").
    """
    local_base_folder = os.getcwd()
    local_git_repo_full_path = f"{local_base_folder}/{code_wiki_name}"

    # json file name containing the API call output for most visited pages
    most_visited_json_name = f"{code_wiki_name}-most-visited.json"
    most_visited_json_full_path = os.path.join(local_git_repo_full_path, most_visited_json_name)

    most_visited_md_name = f"Most-visited-{max_number_of_items_in_md_for_most_visited_pages}-pages-in-last-30-days.md"
    most_visited_md_full_path = os.path.join(local_git_repo_full_path, code_wiki_name, most_visited_md_name)

    new_articles_txt_full_path = None
    new_articles_md_full_path = None
    if do_new_articles == "1":
        new_articles_txt_name = f'{code_wiki_name}-new-articles.txt'
        new_articles_txt_full_path = os.path.join(local_git_repo_full_path, new_articles_txt_name)

        new_articles_md_name = f"Articles-created-in-the-past-{number_of_days_for_new_articles_md}-days.md"
        new_articles_md_full_path = os.path.join(local_git_repo_full_path, code_wiki_name, new_articles_md_name)

    return local_git_repo_full_path, most_visited_json_full_path, most_visited_md_full_path, \
            new_articles_txt_full_path, new_articles_md_full_path


def create_file(file_path):
    """
    Create a file at the specified path, including any necessary parent directories.

    Args:
    file_path (str): The path to the file to be created.

    Returns:
    None

    Creates the specified file at the given path. If the file or any of its parent directories do not exist, it will
    create the necessary directories as well. If the file already exists, it will be replaced with an empty file.
    """
    if not os.path.exists(file_path):
        parent_directory = os.path.dirname(file_path)
        if not os.path.exists(parent_directory):
            os.makedirs(parent_directory)
        open(file_path, "w").close()


def _create_api_call_definitions():
    """
    Create data and headers for an API call.

    Returns:
    tuple: A tuple containing the following elements:
        - post_data (str): JSON-formatted data for the API call, including parameters like pageViewsForDays and continuationToken.
        - headers (dict): Headers specifying the content type and other details for the API call.
    """
    post_data_json = {"pageViewsForDays": 30, "continuationToken": continuation_token}
    post_data = json.dumps(post_data_json)
    headers = {"Content-type": "application/json",
               "Accept": "text/plain",
               "connection": "keep-alive"}
    return post_data, headers


def _configure_api_org_url(project_name, wiki_name_permanent, code_wiki_name):
    """
    Configure and return the URL for making an API call to a specific Azure DevOps Wiki.

    Args:
    project_name (str): The name of the Azure DevOps project.
    wiki_name_permanent (str): The permanent name of the Azure DevOps wiki.
    code_wiki_name (str): The name of the specific code wiki.

    Returns:
    str: The complete URL for the API call to retrieve information from the specified Azure DevOps Wiki.
    """
    organization_url = (f"https://dev.azure.com/{project_name}/{wiki_name_permanent}/_apis/wiki/wikis/"
                        f"{code_wiki_name}/pagesbatch?api-version=7.0")
    return organization_url


def create_most_visited_json(most_visited_json_full_path, project_name, wiki_name_permanent, code_wiki_name,
                             ado_username, pat):
    """
    Create a JSON file containing information about the most visited pages in an Azure DevOps Wiki.

    Args:
    most_visited_json_full_path (str): The full path to the JSON file to be created.
    project_name (str): The name of the Azure DevOps project.
    wiki_name_permanent (str): The permanent name of the Azure DevOps wiki.
    code_wiki_name (str): The name of the specific code wiki.
    ado_username (str): The Azure DevOps username for authentication.
    pat (str): The Personal Access Token (PAT) for authentication.

    Returns:
    None

    This function makes API calls to retrieve information about the most visited pages in an Azure DevOps Wiki.
    It paginates through the results and writes the collected data into a JSON file specified by
    most_visited_json_full_path.
    """
    global continuation_token
    global result_json
    global current_batch_result_json
    global batch_number
    global has_more_results

    colors_worker.prLightPurple(f"Creating most visited json file")

    while True:
        # API call
        try:
            post_data, new_headers = _create_api_call_definitions()
            organization_url = _configure_api_org_url(project_name, wiki_name_permanent, code_wiki_name)

            # Fetch pageable list of Wiki Pages
            resp = requests.post(organization_url, auth=HTTPBasicAuth(ado_username, pat), data=post_data,
                                 headers=new_headers)
            if resp.status_code != 401:
                # in the last "page" batch, we won't get ContinuationToken. So we should check
                if "X-MS-ContinuationToken" in resp.headers:
                    has_more_results = True
                    batch_number = batch_number + 1
                    colors_worker.prLightPurple(f"Response header for X-MS-ContinuationToken: "
                                                f"{resp.headers['X-MS-ContinuationToken']}")
                    continuation_token = resp.headers['X-MS-ContinuationToken']
                else:
                    has_more_results = False
                    break
                current_batch_result_json = resp.text
                str_to_find = '"value":'
                index_value = current_batch_result_json.find(str_to_find)
                current_batch_result_json = current_batch_result_json[(index_value + len(str_to_find)):-1]

                # For the first batch, remove the "]" character at the end, and add "," character
                if batch_number == 1:
                    current_batch_result_json = (current_batch_result_json[:len(current_batch_result_json) - 1] +
                                                 "\n\n,\n\n")
                else:
                    # For all the batches after first batch, remove the "[" character at the beginning
                    # and the "]" character at the end
                    current_batch_result_json = current_batch_result_json[1:-1] + "\n\n,\n\n"

                result_json = result_json + current_batch_result_json
            elif resp.status_code == 401:
                colors_worker.prRed("Authentication error. Exiting ...")
                exit(1)
            else:
                colors_worker.prRed(f"API Error: {resp.status_code}")
                exit(1)
        except Exception as e:
            print("Error: " + e)

    # Remove the last "," and add "]" to the end
    index_of_last_comma = result_json.rfind(',', len(result_json) - 50, len(result_json))
    most_visited_json_content = f"{result_json[:index_of_last_comma]}]"
    with open(most_visited_json_full_path, 'w') as f:
        f.write(most_visited_json_content)


def create_new_articles_txt(number_of_days_for_new_articles_md, new_articles_txt_full_path):
    """
    Create a text file containing information about new articles created within a specific time frame.

    Args:
    number_of_days_for_new_articles_md (int): The number of days for which to retrieve new articles.
    new_articles_txt_full_path (str): The full path to the text file to be created.

    Returns:
    None

    This function generates a text file that contains information about new articles created in a Git repository
    within the specified time frame (number_of_days_for_new_articles_md). It uses a Git command to extract this
    information and writes it to the text file specified by new_articles_txt_full_path.
    """
    command = (f"git log --since='{number_of_days_for_new_articles_md} days ago' "
               f"--pretty='format:#ItemAuthor#%an%n#ItemDate#%cd' --name-only --diff-filter=AR "
               f"--date=format-local:\'%m/%d/%y %H:%M:%S\' -- \'*.md\'")
    git_output = _wrap_git_command(command)

    with open(new_articles_txt_full_path, 'w') as f:
        f.write(git_output.stdout)


def create_new_articles_md(number_of_days_for_new_articles_md, new_articles_txt_full_path, new_articles_md_full_path):
    """
    Create a Markdown file listing new articles added to a wiki within a specified time frame.

    Args:
    number_of_days_for_new_articles_md (int): The number of days for which to retrieve new articles.
    new_articles_txt_full_path (str): The full path to the text file containing information about new articles.
    new_articles_md_full_path (str): The full path to the Markdown file to be created.

    Returns:
    None

    This function processes the information about new articles from the input text file and creates a Markdown file
    that lists the new articles added to a wiki within the specified time frame. It includes details such as page names,
    authors, and dates.
    """
    with open(new_articles_txt_full_path, 'r') as f:
        new_articles_commits = f.read()

    # Split the text output into individual commit logs
    commit_logs = new_articles_commits.strip().split('\n\n')

    # Create a dictionary to hold the earliest commit date for each file
    earliest_dates = {}

    for log in commit_logs:
        # check if log is not empty
        if not log:
            continue

        # Split each commit log into lines
        lines = log.split('\n')

        # Extract the filename, author, and date from the commit log
        filename = lines[-1]
        author = [line for line in lines if line.startswith('#ItemAuthor#')][0][12:]
        date = [line for line in lines if line.startswith('#ItemDate#')][0][10:]

        # If the filename is not in the earliest_dates dictionary yet, add it with the current date
        if filename not in earliest_dates:
            earliest_dates[filename] = date
        else:
            # Otherwise, compare the current date to the earliest date and update if necessary
            earliest_date = earliest_dates[filename]
            if date < earliest_date:
                earliest_dates[filename] = date

    # Print the earliest date for each file
    str_now = datetime.now(timezone.utc).strftime("%c")
    resulting_md = f"Last {number_of_days_for_new_articles_md} pages added to wiki, as of <b> {str_now} UTC : </b> \n\n"
    resulting_md = resulting_md + ' | <b>Page</b> | <b>Author</b> | <b>Date</b> | \n'
    resulting_md = resulting_md + ' | ---- | ------ | ---- | \n'
    current_author_in_iter = ''
    current_date_in_iter = ''
    current_page_in_iteration = ''
    current_page_in_iteration_to_use_in_md = ''

    articles = []  # stores the wiki page names found to check if the page is added before referencing this
    current_number_of_items = 0

    max_number_of_items_in_md_for_last_updated_pages = 2000

    with open (new_articles_txt_full_path, 'r') as f:
        for commit in f:
            if commit.startswith('#ItemAuthor#'):
                current_author_in_iter = commit.replace('#ItemAuthor#', '').replace('\n', '')
            elif commit.startswith('#ItemDate#'):
                current_date_in_iter = commit.replace('#ItemDate#', '').replace('\n', '')
            else:
                current_page_in_iteration = commit.replace('\n', '')
                current_page_in_iteration_to_use_in_md = current_page_in_iteration
                # we should have "-" characters instead of " " characters
                current_page_in_iteration_to_use_in_md = current_page_in_iteration_to_use_in_md.replace(' ', '-')
                if (current_page_in_iteration != '' and resulting_md.find(
                        '[' + current_page_in_iteration_to_use_in_md + ']') < 0 and current_page_in_iteration.find(
                    new_articles_md_full_path) < 0):
                    current_page_in_iteration_to_use_in_md_for_link = current_page_in_iteration_to_use_in_md.replace(
                        '-', ' ').replace('%2D', '-').replace('%3A', ':')

                    # check if the page is already added before
                    if current_page_in_iteration_to_use_in_md not in articles:
                        articles.append(current_page_in_iteration_to_use_in_md)

                        resulting_md = resulting_md + '| [' + \
                        current_page_in_iteration_to_use_in_md_for_link + '](' + \
                        current_page_in_iteration_to_use_in_md + ') |' + current_author_in_iter + '|' + \
                        current_date_in_iter + '\n'
                        current_number_of_items = current_number_of_items + 1

                        # check if max is reached
                        if current_number_of_items == int(max_number_of_items_in_md_for_last_updated_pages):
                            break

    resulting_md = resulting_md.replace('||', '|')

    with open(new_articles_md_full_path, 'w') as f:
        f.write(resulting_md)


def _sortByViewCountTotal(e):
    """Used for sorting the list by 'viewCountTotal'"""
    return e['viewCountTotal']


def create_most_visited_md(most_visited_json_full_path, most_visited_md_full_path, number_of_items_for_most_visited_md):
    """
    Create a Markdown file listing the most visited pages in an Azure DevOps Wiki.

    Args:
    most_visited_json_full_path (str): The full path to the JSON file containing information about page views.
    most_visited_md_full_path (str): The full path to the Markdown file to be created.
    number_of_items_for_most_visited_md (int): The number of top pages to include in the Markdown file.

    Returns:
    None

    This function processes the JSON data containing page views, filters out pages without view statistics,
    calculates the total view counts for each page, and creates a Markdown file that lists the most visited pages
    in the Azure DevOps Wiki. It includes details such as page paths, view counts, and article summaries.
    """
    with open(most_visited_json_full_path) as f:
        most_visited_json = json.load(f)

    # Loop through the rows and remove the pages without viewStats
    page_info_list_without_view_stats = []
    for item in most_visited_json:
        page_detail = {'id': None, "path": None, "viewStats": None,
                       'id': item['id'], 'path': item['path']}
        if "viewStats" in item:
            if not (str(item['viewStats']) == '[]'):
                page_detail['viewStats'] = item['viewStats']

                page_info_list_without_view_stats.append(page_detail)

    # Loop through the rows and parse the viewStats and get the total view counts per row
    page_info_list = []
    for item in page_info_list_without_view_stats:  # item ==> main row
        page_detail = {"id": None, "path": None, "viewCountTotal": 0,
                       'id': item['id'], 'path': item['path']}
        tmp_count = 0
        current_rows_view_stats = item['viewStats']
        for item2 in current_rows_view_stats:  # item2 ==> inner rows in viewStats
            tmp_count = tmp_count + int(item2['count'])
        page_detail['viewCountTotal'] = tmp_count
        page_info_list.append(page_detail)

    # Sort by viewCountTotal
    page_info_list.sort(reverse=True, key=_sortByViewCountTotal)

    # Get "Now" in UTC to use in the generated MD
    str_now = datetime.now(timezone.utc).strftime("%c")

    resulting_md = (f"Most visited {str(number_of_items_for_most_visited_md)} "
                   f"pages in last 30 days as of <b>{str_now} UTC </b> \n\n")
    resulting_md = resulting_md + ' | <b>Path</b> | <b>Page Visits</b> | <b>Article Summary</b> |\n'
    resulting_md = resulting_md + ' | ---- | ------ | ------ |\n'
    tmp_count = 1
    for item in page_info_list:
        if tmp_count <= int(number_of_items_for_most_visited_md):
            tmp_count = tmp_count + 1

            tmp_path = str(item['path'])
            tmp_path = tmp_path[1:len(tmp_path)]  # remove the 1st character which is a  "/"

            tmp_path = tmp_path.replace('-', '%2D')
            tmp_path = tmp_path.replace(' ', '-')

            tmp_path_link_name = str(item['path'])  # path to be used in the MD link
            # remove the 1st character which is a  "/"
            tmp_path_link_name = tmp_path_link_name[1:len(tmp_path_link_name)]
            # in case if wiki author used | character in the path (title)
            tmp_path_link_name = tmp_path_link_name.replace('|','%7C')
            tmp_path = tmp_path.replace('|', '%7C')

            if "*" in tmp_path:
                tmp_path = tmp_path.replace('*', '%2A')
            if "|" in tmp_path:
                tmp_path = tmp_path.replace('|', '%7C')
            if ":" in tmp_path:
                tmp_path = tmp_path.replace(':', '%3A')

            resulting_md = resulting_md +  \
                           (f" | [{tmp_path_link_name}]({tmp_path}.md) | "
                            f"{str(item['viewCountTotal'])} | "
                            f"{str(return_summary(re.sub(r'[^/]+$', '', most_visited_md_full_path) + (tmp_path + '.md')))} |"
                            f"\n")

    with open(most_visited_md_full_path, 'w') as f:
        f.write(resulting_md)


def _wrap_git_command(command):
    """
    Execute a Git command and handle the results.

    Args:
    command (str): The Git command to be executed.

    Returns:
    subprocess.CompletedProcess: The result of the Git command execution.

    This function executes a Git command specified by the 'command' argument. It handles the command's execution and
    provides feedback on success or failure. If the command succeeds, it returns a subprocess.CompletedProcess object
    containing the result. If the command fails, it displays an error message and returns None.
    """
    try:
        # Set the default branch name to "main" globally
        if command == 'git init':
            subprocess.run(['git', 'config', '--global', 'init.defaultBranch', 'main'], check=True)

        my_proc = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, universal_newlines=True)
        if my_proc.returncode == 0:
            colors_worker.prGreen(f"Git command '{command}' succeeded")
            return my_proc
    except subprocess.CalledProcessError:
        colors_worker.prRed(f"Git command '{command}' failed")
        return


def _initialize_git_repo():
    """
    Initialize a Git repository if not already initialized.

    Args:
    None

    Returns:
    None

    This function checks if a Git repository is already initialized by running 'git status'. If not, it initializes
    a new Git repository using 'git init'. It does not take any arguments and returns None.
    """
    _wrap_git_command('git status')
    _wrap_git_command('git init')


def configure_git_user(local_git_repo_full_path, ado_username):
    """
    Configure the Git user for a local repository at the given path.

    Args:
    local_git_repo_full_path (str): The full path to the local Git repository.
    ado_username (str): The Azure DevOps username to set as the Git user.

    Returns:
    None

    This function configures the Git user for the specified local Git repository. It sets the Git user's name to the
    provided Azure DevOps username and the email address to the same username. The Git user is identified as
    "username via Wiki Automation" in the Git configuration. It ensures that the Git user's name and email are correctly
    set for the repository.
    """
    os.chdir(local_git_repo_full_path)
    _initialize_git_repo()

    # wipe existing user config
    _wrap_git_command(f'git config --unset user.name')
    _wrap_git_command(f'git config --unset user.email')

    extract_username = lambda email: (re.search(r'([^@]+)@', email)
                                      .group(1)) if re.search(r'([^@]+)@', email) else None
    name = extract_username(ado_username)

    _wrap_git_command(f'git config user.name "{name} via Wiki Automation"')
    _wrap_git_command(f'git config user.email "{ado_username}"')


def set_remote_origin(local_git_repo_full_path, repo_url):
    """
    Set the remote Git repository's origin URL for a local repository.

    Args:
    local_git_repo_full_path (str): The full path to the local Git repository.
    repo_url (str): The URL of the remote Git repository.

    Returns:
    None

    This function sets the origin URL for the remote Git repository associated with the specified local Git repository.
    If no remote repository is configured, it adds a new remote named 'origin' with the provided 'repo_url'. If a remote
    named 'origin' already exists, it updates its URL to the provided 'repo_url'.
    """
    os.chdir(local_git_repo_full_path)
    remote_exists = _wrap_git_command("git remote -v")
    if remote_exists.stdout == "":
        _wrap_git_command(f'git remote add origin {repo_url}')
    _wrap_git_command(f'git remote set-url origin {repo_url}')


def _get_auth_config(pat):
    """
    Generate the authentication configuration for a Personal Access Token (PAT).

    Args:
    pat (str): The Personal Access Token (PAT) used for authentication.

    Returns:
    str: The authentication configuration string.

    This function takes a Personal Access Token (PAT) as input and generates the authentication configuration required for
    making requests to an API. It encodes the PAT in Base64 and constructs the necessary authentication configuration
    string in the format 'Authorization: Basic <encoded_token>'.
    """
    encoded_part = base64.b64encode(f":{pat}".encode('utf-8')).decode('utf-8')
    auth_config = f"Authorization: Basic {encoded_part}"
    return auth_config


def clone_wiki_repo(repo_url, pat, local_git_repo_full_path):
    """
    Clone a remote Git repository containing a Wiki using a Personal Access Token (PAT).

    Args:
    repo_url (str): The URL of the remote Git repository to clone.
    pat (str): The Personal Access Token (PAT) used for authentication.
    local_git_repo_full_path (str): The full path to the local Git repository where the Wiki will be cloned.

    Returns:
    None

    This function clones a remote Git repository, typically containing a Wiki, to the specified local directory.
    It uses a Personal Access Token (PAT) for authentication and sets an additional authentication header with the PAT.
    """
    auth_header = f'http.extraHeader="{_get_auth_config(pat)}"'
    os.chdir(local_git_repo_full_path)
    _wrap_git_command(f'git -c {auth_header} clone {repo_url}')


def add_commit_md_file(file_path):
    """
    Stage and commit a Markdown file in a local Git repository.

    Args:
    file_path (str): The path to the Markdown file to be staged and committed.

    Returns:
    None

    This function stages the specified Markdown file and commits it to the local Git repository. The commit message is set
    as 'Wiki Automation update via pipeline'.
    """
    os.chdir(os.path.dirname(file_path))
    _wrap_git_command(f"git add '{file_path}'")
    _wrap_git_command(f"git commit -m 'Wiki Automation update via pipeline'")


def push_to_remote_repo(ado_username, pat, remote_url):
    """
    Push local Git changes to a remote repository using Azure DevOps credentials.

    Args:
    ado_username (str): The Azure DevOps username or email.
    pat (str): The Personal Access Token (PAT) for authentication.
    remote_url (str): The URL of the remote repository.

    Returns:
    None

    This function encodes the Azure DevOps username, appends it to the remote URL along with the PAT, and uses Git to push
    local changes to the specified remote repository.
    """
    # encode email so that it can be used in the command line
    encoded_email = urllib.parse.quote(ado_username, safe='')
    transformed_url = remote_url.split('@dev.azure.com')[-1]
    remote_url_with_pat = f"https://{encoded_email}:{pat}@dev.azure.com{transformed_url}"
    _wrap_git_command(f"git push {remote_url_with_pat}")


def main():
    args = parse_args()

    # Create files definitions
    local_git_repo_full_path, \
        most_visited_json_full_path, \
        most_visited_md_full_path, \
        new_articles_txt_full_path, \
        new_articles_md_full_path = \
        create_files_definitions(args.code_wiki_name, args.number_of_days_for_most_visited_md,
                                 args.number_of_days_for_new_articles_md, args.do_new_articles)

    # check if local_git_repo_full_path exists and create if it doesn't
    if not os.path.exists(local_git_repo_full_path):
        os.mkdir(local_git_repo_full_path)
    configure_git_user(local_git_repo_full_path, args.ado_username)

    # Cloning wiki repo
    repo_url = f"https://{args.project_name}@dev.azure.com/{args.project_name}/{args.wiki_name}/_git/" \
               f"{args.code_wiki_name}"
    set_remote_origin(local_git_repo_full_path, repo_url)

    # check if wiki is already cloned
    if not os.path.exists(local_git_repo_full_path + '/' + args.code_wiki_name):
        clone_wiki_repo(repo_url, args.pat, local_git_repo_full_path)

    create_most_visited_json(most_visited_json_full_path,
                             args.project_name,
                             args.wiki_name,
                             args.code_wiki_name,
                             args.ado_username,
                             args.pat)

    create_most_visited_md(most_visited_json_full_path,
                           most_visited_md_full_path,
                           args.number_of_items_for_most_visited_md)

    add_commit_md_file(most_visited_md_full_path)

    push_to_remote_repo(args.ado_username, args.pat, repo_url)

    if args.do_new_articles == '1':
        os.chdir(f"{local_git_repo_full_path}/{args.code_wiki_name}")
        create_new_articles_txt(args.number_of_days_for_new_articles_md, new_articles_txt_full_path)
        create_new_articles_md(args.number_of_days_for_new_articles_md, new_articles_txt_full_path,
                               new_articles_md_full_path)
        add_commit_md_file(new_articles_md_full_path)
        push_to_remote_repo(args.ado_username, args.pat, repo_url)


if __name__ == "__main__":
    main()