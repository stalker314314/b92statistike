Vagrant.configure("2") do |config|

    config.vm.box = "trusty64"
    config.vm.box_url = "https://cloud-images.ubuntu.com/vagrant/trusty/current/trusty-server-cloudimg-amd64-vagrant-disk1.box"

    config.vm.provider :virtualbox do |v|
        v.customize ["modifyvm", :id, "--memory", "2048"]
        v.customize ["modifyvm", :id, "--natdnshostresolver1", "on"]
        v.cpus = 2
    end

    config.vm.box = "ubuntu14"
    config.vm.provision :shell, path: "setup_vagrant.sh"

    # sync folders
    config.vm.synced_folder "./", "/home/vagrant/b92statistike", create:true
    
    config.vm.define "p0" do |p0|
      p0.vm.hostname = "p0"
      p0.vm.box = "p0"
      p0.vm.network :private_network, ip: "192.168.60.10"
      p0.vm.network "forwarded_port", guest: 27017, host: 27017
    end
end

