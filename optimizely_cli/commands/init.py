import click
import getpass
import json
import os
import requests

from optimizely_cli import main
from optimizely_cli import repo
from optimizely_cli.api import client as api_client


def verify_token(token):
    try:
        resp = requests.get(
            'https://api.optimizely.com/v2/projects',
            params={'per_page': 1},
            headers={'Authorization': 'Bearer {}'.format(token)}
        )
        resp.raise_for_status()
    except Exception as e:
        print e
        return False
    return True


@main.cli.command()
@click.option(
    '-n', '--project-name',
    help='Project name',
)
@click.option(
    '-i', '--project-id',
    help='Project ID',
)
@click.option(
    '-c', '--create', is_flag=True,
    help="Create a new project",
)
@click.pass_obj
def init(project, project_name, project_id, create):
    """Link an Optimizely project with your repository"""

    store_credentials = False
    token = project.token
    if project.credentials_path:
        click.echo('Credentials found in {}'.format(project.credentials_path),
                   err=True)
    if not token:
        click.echo('First visit https://app.optimizely.com/v2/profile/api '
                   'to create a new access token')
        token = getpass.getpass('Enter the token you created here: ')
        store_credentials = True

    # make sure the token actually works
    click.echo('Verifying token...')
    if verify_token(token):
        click.echo('Token is valid')
    else:
        click.echo('Invalid token, try again.')
        click.echo('Maybe you copy/pasted the wrong thing?')
        return

    if store_credentials:
        # create the credentials file user-readable/writable only (0600)
        fdesc = os.open(repo.CREDENTIALS_FILE, os.O_WRONLY | os.O_CREAT, 0o600)
        with os.fdopen(fdesc, 'w') as f:
            json.dump({'token': token}, f, indent=4, separators=(',', ': '))
        click.echo('Credentials written to {}'.format(repo.CREDENTIALS_FILE))
        click.echo('Do not add this file to version control!')
        click.echo('It should stay private\n')

    if project.platform and project.project_id:
        click.echo('Config successfully loaded')
        click.echo('You are all set up and ready to go')
        return

    client = api_client.ApiClient(token)

    if not project_name:
        project_name = project.detect_repo_name()
    detected_language = project.detect_project_language()
    if project_id:
        click.echo("Checking for an existing project with ID {}...".format(project_id))
    else:
        click.echo("Checking for an existing project named '{}'...".format(project_name))
    projects = client.list_projects()
    if project_id:
      discovered_projects = [
          p
          for p in projects
          if p.id == int(project_id)
      ]
    else:
      discovered_projects = [
          p
          for p in projects
          if p.name == project_name
      ]
    if len(discovered_projects) > 1 and detected_language:
      # try filtering down by platform if there is more than one
      discovered_projects = [
          p
          for p in discovered_projects
          if p.platform_sdk == detected_language
      ]
    if discovered_projects:
        project.project_id = discovered_projects[0].id
        project.platform = discovered_projects[0].platform_sdk
        click.echo('Found project (id: {})'.format(project.project_id))
    elif create and project_name and detected_language:
        # create the project
        new_project = client.create_project(
            platform=detected_language,
            name=project_name
        )

        if not new_project:
            click.echo('Unable to create a new project')
            return

        project_id = new_project.id
        if project_id:
            project.project_id = project_id
            project.platform = detected_language
            click.echo('Successfully created project (id: {})'.format(
                       project_id))
    else:
      if project_id:
          click.echo('No project found with id: {}'.format(project_id))
      else:
          click.echo('No project found with name: {}'.format(project_name))
      click.echo('Use -p <project_name> or -i <project_id> to use an existing project or -c to create a new one')
      return

    # write the config file so we have baseline context
    config = {
        'project_id': project.project_id,
        'platform': project.platform,
    }
    project.save_config(config, echo=True)
