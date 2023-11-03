# Azure DevOps Wiki Page View Statistics Reporter

This Python script retrieves page view statistics for Azure DevOps wiki articles and generates a report of the most visited articles. The script uses the Azure DevOps REST API to retrieve the page view data, and outputs the report back to the Azure Devops wiki space. Produced markdown files are then pushed to the Azure DevOps wiki repository.

## Requirements
To use this script, you will need:

- Python 3.x
- An Azure DevOps account
- Personal access token (PAT) with the appropriate permissions to access the Azure DevOps REST API

## Installation
1. Clone the repository or download the source code to your local machine.
2. Install the required Python packages by running the following command in the terminal: `pip install -r requirements.txt`

## Usage
To use the script, run the following command in the terminal:

`python main.py <organization> <project> <wiki-name> <account_name> <PAT> <number_of_items_for_most_visited_md> <number_of_days_for_most_visited_md> <do_new_articles> <--number_of_days_for_new_articles_md=n>`

Example:

`python main.py Security-Org Security%20Protection Defender%20Protection username@org.com xxxyyy 10 10 1 --number_of_days_for_new_articles_md=60`

Where:

- **organization**: The name of your Azure DevOps organization.
- **project**: The name of the Azure DevOps project.
- **wiki-name**: The name of the Azure DevOps wiki.
- **account_name**: The name of the Azure DevOps account.
- **PAT**: The personal access token (PAT) with the appropriate permissions to access the Azure DevOps REST API.
- **number_of_items_for_most_visited_md**: Number of items (x) in Most-visited-x-pages-in-last-y-days.md file 
- **number_of_days_for_most_visited_md**: Number of days (y) in Most-visited-x-pages-in-last-y-days.md
- **do_new_articles**: A flag indicating whether to generate new articles (values: 0 and 1)
- **number_of_days_for_new_articles_md**: The number of days for new articles. If not specified, the default value is 30 days.
