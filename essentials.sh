sudo add-apt-repository universe
sudo apt update

sudo apt install debootstrap xserver-xephyr x11-xserver-utils xterm

sudo apt update && sudo apt install -y debootstrap squashfs-tools \
xorriso grub-pc-bin grub-efi-amd64-bin qemu-system-x86 qemu-kvm \
xserver-xephyr python3-tk