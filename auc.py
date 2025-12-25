import tkinter as tk
from tkinter import messagebox
import os
import subprocess

PROJECT = os.path.abspath("projects/ubuntu-debootstrap")
ROOTFS = os.path.join(PROJECT, "rootfs")
ISO_STAGING = os.path.join(PROJECT, "iso_staging")
OUTPUT_ISO = os.path.join(PROJECT, "custom-ubuntu.iso")

def run_as_sudo(cmd):
    return subprocess.run(f"sudo -E {cmd}", shell=True, check=True)

def bootstrap_system():
    try:
        # 1. CLEANUP: Ensure a fresh start to remove failed lightdm configs
        print("Cleaning up old project files...")
        run_as_sudo(f"umount -lf {ROOTFS}/* || true")
        run_as_sudo(f"rm -rf {ROOTFS}")
        os.makedirs(PROJECT, exist_ok=True)
        
        # 2. BASE BOOTSTRAP
        print("Starting debootstrap...")
        run_as_sudo(f"debootstrap --variant=minbase noble {ROOTFS} http://archive.ubuntu.com/ubuntu/")
        
        # 3. CONFIGURE REPOSITORIES & DNS
        run_as_sudo(f"cp /etc/resolv.conf {ROOTFS}/etc/resolv.conf")
        sources = "deb http://archive.ubuntu.com/ubuntu/ noble main restricted universe multiverse\n"
        sources += "deb http://archive.ubuntu.com/ubuntu/ noble-updates main restricted universe multiverse\n"
        with open("temp_sources.list", "w") as f: f.write(sources)
        run_as_sudo(f"mv temp_sources.list {ROOTFS}/etc/apt/sources.list")

        # 4. INSTALL DESKTOP & SLIM (Lighter Login Manager)
        # We include 'xinit' and 'slim' to fix the previous errors
        setup_cmd = f"""
        chroot {ROOTFS} /bin/bash -c '
            apt update
            apt install -y --no-install-recommends \
                linux-image-generic casper grub-pc-bin grub-efi-amd64-bin \
                network-manager xfce4 xfce4-terminal dbus-x11 sudo \
                xserver-xorg-video-all xserver-xorg-input-all xserver-xorg-core \
                init xinit slim
            
            # Create user 'ubuntu'
            useradd -m -s /bin/bash ubuntu
            echo "ubuntu:ubuntu" | chpasswd
            usermod -aG sudo ubuntu

            # Configure Autologin for SLiM
            sed -i "s/^#default_user.*/default_user        ubuntu/" /etc/slim.conf
            sed -i "s/^#auto_login.*/auto_login           yes/" /etc/slim.conf
        '
        """
        run_as_sudo(setup_cmd)
        messagebox.showinfo("Success", "System bootstrapped with SLiM autologin!\nUser: ubuntu | Pass: ubuntu")
        
    except Exception as e:
        messagebox.showerror("Error", f"Bootstrap failed: {e}")

def gui_chroot():
    # Setup mounts for the customization window
    run_as_sudo(f"cp /etc/resolv.conf {ROOTFS}/etc/resolv.conf")
    mounts = ["dev", "dev/pts", "proc", "sys", "run", "dev/shm"]
    for fs in mounts:
        target = f"{ROOTFS}/{fs}"
        run_as_sudo(f"mkdir -p {target}")
        run_as_sudo(f"mount --bind /{fs} {target} || true")

    subprocess.Popen("Xephyr :2 -screen 1280x720 -ac -br", shell=True)
    chroot_cmd = f"""
    sudo chroot {ROOTFS} /bin/bash -c '
        export DISPLAY=:2
        export XDG_RUNTIME_DIR=/tmp/runtime-auc
        export LIBGL_ALWAYS_SOFTWARE=1
        mkdir -p $XDG_RUNTIME_DIR && chmod 700 $XDG_RUNTIME_DIR
        if [ ! -f /var/lib/dbus/machine-id ]; then dbus-uuidgen > /var/lib/dbus/machine-id; fi
        dbus-run-session -- startxfce4
    '
    """
    subprocess.Popen(chroot_cmd, shell=True)

def build_iso():
    try:
        # Cleanup mounts before Squashing
        for fs in ["dev/pts", "dev/shm", "dev", "proc", "sys", "run"]:
            run_as_sudo(f"umount -lf {ROOTFS}/{fs} || true")
        
        run_as_sudo(f"rm -rf {ISO_STAGING}")
        os.makedirs(os.path.join(ISO_STAGING, "casper"), exist_ok=True)
        
        print("Creating SquashFS...")
        run_as_sudo(f"mksquashfs {ROOTFS} {ISO_STAGING}/casper/filesystem.squashfs -comp xz")
        
        # Copy latest kernel/initrd
        run_as_sudo(f"cp $(ls -v {ROOTFS}/boot/vmlinuz-* | tail -1) {ISO_STAGING}/casper/vmlinuz")
        run_as_sudo(f"cp $(ls -v {ROOTFS}/boot/initrd.img-* | tail -1) {ISO_STAGING}/casper/initrd")
        
        os.makedirs(os.path.join(ISO_STAGING, "boot/grub"), exist_ok=True)
        grub_conf = """
set default=0
set timeout=1
menuentry "My Custom Ubuntu (XFCE)" {
    linux /casper/vmlinuz boot=casper quiet splash ---
    initrd /casper/initrd
}
"""
        with open("temp_grub.cfg", "w") as f: f.write(grub_conf)
        run_as_sudo(f"mv temp_grub.cfg {ISO_STAGING}/boot/grub/grub.cfg")
        
        print("Generating ISO...")
        run_as_sudo(f"grub-mkrescue -o {OUTPUT_ISO} {ISO_STAGING}")
        messagebox.showinfo("Done", f"ISO built at {OUTPUT_ISO}")
    except Exception as e:
        messagebox.showerror("Build Error", str(e))

def launch_qemu():
    # Use 4G RAM and virtio graphics for best performance
    qemu_cmd = f"qemu-system-x86_64 -enable-kvm -m 4G -cdrom {OUTPUT_ISO} -vga virtio -display gtk,zoom-to-fit=on"
    subprocess.Popen(qemu_cmd, shell=True)

# --- UI WINDOW ---
root = tk.Tk()
root.title("AUC: Advanced Ubuntu Customizer")
root.geometry("400x350")

tk.Label(root, text="Custom Ubuntu Builder", font=("Arial", 14, "bold")).pack(pady=10)

buttons = [
    ("1. Bootstrap (Start Here)", bootstrap_system),
    ("2. Customize (Xephyr)", gui_chroot),
    ("3. Build Final ISO", build_iso),
    ("4. Test in QEMU", launch_qemu)
]

for text, func in buttons:
    btn = tk.Button(root, text=text, command=func, height=2)
    btn.pack(fill="x", padx=20, pady=5)
    if text.startswith("4"):
        btn.config(bg="green", fg="white")

root.mainloop()