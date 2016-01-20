sudo apt-get update

# Install all packages
sudo apt-get -y install tor git python-pip privoxy

# Update tor configuration with password
if ! grep -Gq "^ControlPort" /etc/tor/torrc
then
	hash=`tor --quiet --hash-password 12345`
	echo "ControlPort 9051" | sudo tee -a /etc/tor/torrc >> /dev/null
	echo "HashedControlPassword" $hash | sudo tee -a /etc/tor/torrc >> /dev/null
	echo "CookieAuthentication 1" | sudo tee -a /etc/tor/torrc >> /dev/null
	echo "CookieAuthFileGroupReadable 1" | sudo tee -a /etc/tor/torrc >> /dev/null
	sudo /etc/init.d/tor restart
fi

# Configure privoxy to use tor
echo "forward-socks5 / localhost:9050 ." | sudo tee -a /etc/privoxy/config >> /dev/null
# Privoxy blocking is not needed (in fact, it does block some URLs like:
# http://bulevar.b92.net/pop-kultura.php?yyyy=2015&mm=06&dd=03&nav_id=999976
sudo mv /etc/privoxy/default.action /etc/privoxy/default.action.bak
sudo touch /etc/privoxy/user.action
sudo /etc/init.d/privoxy restart

# Installing needed python libraries
git clone git://github.com/aaronsw/pytorctl.git
sudo pip install pytorctl/
sudo pip install beautifulsoup4
sudo pip install python-dateutil
sudo pip install tzlocal
sudo pip install emoji

# Install Mongo
sudo apt-get -y install mongodb
sudo sed -i 's/^bind_ip\s*=\s*.*$/bind_ip = 0.0.0.0/' /etc/mongodb.conf
sudo service mongodb restart
sudo pip install pymongo

# Install support for mongo2sql
sudo apt-get -y install python-dev unixodbc unixodbc-dev freetds-dev
sudo pip install pymssql