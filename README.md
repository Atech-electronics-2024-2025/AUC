# AUC
Ever wanted CUBIC (Custom Ubuntu ISO Creator) but better, less CLI, more GUI? Well then, AUC: Advanced Ubuntu Customizer has got your back! However, it only works with desktop enviroments easy to chroot in, specifically XFCE. You can now create Ubuntu-based Linux distros  via AUC by chrooting into the desktop with only 1 click,  and customize all!


# WAIT! Before running the .py file as the app, install these dependncies first by running this command:

sudo apt update && sudo apt install -y debootstrap squashfs-tools \
xorriso grub-pc-bin grub-efi-amd64-bin qemu-system-x86 qemu-kvm \
xserver-xephyr python3-tk

Without this, the app will not function correctly.
