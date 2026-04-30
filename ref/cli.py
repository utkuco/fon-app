import click
from datetime import date, datetime
from  downloadkap.downloadpdfs import start_download


@click.command()
@click.option('--start_date', default=None, help='Enter start date in YYYY-MM-DD format i. e. 2017-04-24')
@click.option('--end_date', default=None, help='Enter end date in YYYY-MM-DD format i. e. 2017-04-24')
@click.option('--download_directory', default='./Downloads', help="Enter path to download folder")
def enter(start_date, end_date, download_directory):
    if (start_date is None):
        start_date = date.today()
    else:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        except ValueError:
            raise click.BadParameter(
                'Wromg date format!\nEnter start date in YYYY-MM-DD format i. e. 2017-04-24\nYou entered: {}'.format(
                    start_date), param_hint=['--start_date'])

    if (end_date is None):
        end_date = date.today()
    else:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            raise click.BadParameter(
                'Wromg date format!\nEnter end date in YYYY-MM-DD format i. e. 2017-04-24\nYou entered: {}'.format(
                    end_date), param_hint=['--end_date'])

    click.echo('Download all pdf attachments from {} to {} and save to {} folder!'.format(start_date, end_date,
                                                                                          download_directory))

    start_download(start_date, end_date, download_directory)
