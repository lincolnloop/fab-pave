from fabric.api import *
from fabric.contrib.files import *


env.apache_port = 9000
env.fqdn = 'my-host.my-domain.com'
env.admin_user = 'admin'


def pave_server():
    env.user = create_first_user()
    configure_sshd()
    set_hostname()
    software_update()
    configure_firewall
    configure_mail()
    install_nginx()
    install_apache()
    install_postgres()
    install_geodjango()

def create_first_user():
    env.user = 'root'
    username = prompt('Specify a username: ', default=env.admin_user)
    password = prompt('Specify a password for %s: ' % username)
    run('useradd -d /home/%s -s /bin/bash -m %s' % (username, username))
    # hacky way to set password via stdin
    run('yes %s | passwd %s' % (password, username))
    # clear history
    run('history -c')
    append('%s\tALL=(ALL) ALL' % username, '/etc/sudoers')
    # TODO change root password, upload ssh key
    return username
    
def configure_sshd():
    # TODO block root login, change port
    pass

def set_hostname():
    """Setup hostname and FQDN in /etc/hostname and /etc/hosts.conf"""
    # TODO add a regex here to verify a proper fqdn was entered
    env.fqdn = prompt('Specify a fully qualified domain name (FQDN): ', 
                      default=env.fqdn)
    # technically, an FQDN should have a trailing period, but we don't need it
    env.fqdn.strip('.')
    if '.' in env.fqdn:
        hostname_tuple = env.fqdn.split('.')
        hostname_guess = hostname_tuple[0]
        domain_name_guess = '.'.join(hostname_tuple[1:])
    else:
        hostname_guess = 'my-host'
        domain_name_guess = 'my-domain.com'
    hostname = prompt('Specify a hostname: ', default=hostname_guess)
    domain_name = prompt('Specify a domain name: ', default=domain_name_guess)
    sudo('hostname %s' % hostname)
    sudo('echo %s > /etc/hostname' % hostname)
    sudo('echo %s > /etc/mailname' % domain_name)
    conf_file = '/etc/hosts'
    upload_template('templates/%s' % conf_file, 
                    conf_file,
                    context={'hostname': hostname, 'fqdn': env.fqdn},
                    use_sudo=True) 


def software_update():
    """Update package list and apply all available updates"""
    sudo('aptitude update -q -y')
    sudo('aptitude safe-upgrade -q -y')
    # setup build enviroment
    sudo('chown %s /usr/local/src' % env.user)
    sudo('aptitude install -q -y build-essential')
    
def configure_firewall():
    # TODO setup UFW
    pass


def configure_mail():
    """Setup an SMTP server only accessible to localhost"""
    conf_file = '/etc/exim4/update-exim4.conf.conf'
    put('templates%s' % conf_file, '/tmp/')
    sudo('mv /tmp/update-exim4.conf.conf %s' % conf_file)
    sudo('update-exim4.conf')
    
    
def install_nginx():
    """Installs Nginx web server"""
    sudo('aptitude install -q -y  nginx')
    # TODO configs

def install_apache():
    """Installs Apache/mod-wsgi"""
    sudo('aptitude install -q -y apache2-mpm-worker libapache2-mod-wsgi')
    conf_file = '/etc/apache2/ports.conf'
    upload_template('templates%s' % conf_file, 
                    conf_file,
                    context = {'port': env.apache_port},
                    use_sudo = True) 
    append('\nServerName %s' % env.fqdn, 
           '/etc/apache2/apache2.conf', 
           use_sudo=True)
    sudo('/etc/init.d/apache2 restart')

def install_postgres():
    """Install Postgres 8.3"""
    sudo('aptitude install -q -y postgresql-8.3') 
    # use md5 auth
    conf_file = '/etc/postgresql/8.3/main/pg_hba.conf'
    sed(conf_file, 
        '^\(local\s\+all\s\+all\s\+\)ident\ssameuser\s*$',
        '\1md5',
        use_sudo=True)
    
    
def install_geodjango():
    install_geos()
    install_proj4()
    install_postgis()
    install_gdal()

def install_geos():
    """Install GEOS 3.2.1"""
    with cd('/usr/local/src'):
        run('wget -q http://download.osgeo.org/geos/geos-3.2.1.tar.bz2')
        run('tar xjf geos-3.2.1.tar.bz2 && rm geos-3.2.1.tar.bz2')
        with cd('geos-3.2.1'):
            run('./configure')
            run('make')
            sudo('make install')

def install_proj4():
    """Install Proj 4.7"""
    with cd('/usr/local/src'):
        run('wget -q http://download.osgeo.org/proj/proj-4.7.0.tar.gz')
        run('http://download.osgeo.org/proj/proj-datumgrid-1.5.zip')
        run('tar xzf proj-4.7.0.tar.gz && rm proj-4.7.0.tar.gz')
        with cd('proj-4.7.0/nad'):
            run('unzip ../../proj-datumgrid-1.5.zip && rm ../../proj-datumgrid-1.5.zip')
        with cd('proj-4.7.0'):
            run('./configure')
            run('make')
            sudo('make install')

def install_postgis():
    """Install PostGIS 1.5.1"""
    sudo('aptitude install -q -y libxml2-dev postgresql-server-dev-8.3')
    with cd('/usr/local/src'):
        run('wget -q http://postgis.refractions.net/download/postgis-1.5.1.tar.gz')
        run('tar xzf postgis-1.5.1.tar.gz && rmpostgis-1.5.1.tar.gz')
        with cd('postgis-1.5.1'):
            run('./configure')
            run('make')
            sudo('make install')
    sudo('ldconfig')
    with sudo('su - postgres'):
        run('createdb -E UTF8 template_postgis')
        run('createlang -d template_postgis plpgsql')
        run('psql -d postgres -c "UPDATE pg_database SET datistemplate=\'true\' WHERE datname=\'template_postgis\';"')
        run('psql -d template_postgis -f `pg_config --sharedir`/contrib/postgis-1.5/postgis.sql')
        run('psql -d template_postgis -f `pg_config --sharedir`/contrib/postgis-1.5/spatial_ref_sys.sql')
        run('psql -d template_postgis -c "GRANT ALL ON geometry_columns TO PUBLIC;"')
        run('psql -d template_postgis -c "GRANT ALL ON geography_columns TO PUBLIC;"')
        run('psql -d template_postgis -c "GRANT ALL ON spatial_ref_sys TO PUBLIC;"')
        

def install_gdal():
    """Install GDAL 1.7.1"""
    with cd('/usr/local/src'):
        run('wget -q http://download.osgeo.org/gdal/gdal-1.7.1.tar.gz')
        run('tar xzf gdal-1.7.1.tar.gz && rm gdal-1.7.1.tar.gz')
        with cd('gdal-1.7.1'):
            run('./configure')
            run('make')
            sudo('make install')
    sudo('ldconfig')