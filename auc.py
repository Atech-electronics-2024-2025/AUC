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
        run_as_sudo(f"umount -lf {ROOTFS}/* || true")
        run_as_sudo(f"rm -rf {ROOTFS}")
        os.makedirs(PROJECT, exist_ok=True)
        run_as_sudo(f"debootstrap --variant=minbase noble {ROOTFS} http://archive.ubuntu.com/ubuntu/")
        
        run_as_sudo(f"cp /etc/resolv.conf {ROOTFS}/etc/resolv.conf")
        sources = "deb http://archive.ubuntu.com/ubuntu/ noble main restricted universe multiverse\n"
        with open("temp_sources.list", "w") as f: f.write(sources)
        run_as_sudo(f"mv temp_sources.list {ROOTFS}/etc/apt/sources.list")

        setup_cmd = f"""
        chroot {ROOTFS} /bin/bash -c '
            apt update
            apt install -y --no-install-recommends \
                linux-image-generic casper grub-pc-bin grub-efi-amd64-bin \
                network-manager xfce4 xfce4-terminal dbus-x11 sudo \
                xserver-xorg-video-all xserver-xorg-input-all xserver-xorg-core \
                init xinit slim
            
            useradd -m -s /bin/bash ubuntu
            echo "ubuntu:ubuntu" | chpasswd
            usermod -aG sudo ubuntu

            sed -i "s/^#default_user.*/default_user        ubuntu/" /etc/slim.conf
            sed -i "s/^#auto_login.*/auto_login           yes/" /etc/slim.conf
        '
        """
        run_as_sudo(setup_cmd)
        messagebox.showinfo("Success", "Bootstrap complete!")
    except Exception as e:
        messagebox.showerror("Error", f"Bootstrap failed: {e}")

def gui_chroot():
    run_as_sudo(f"cp /etc/resolv.conf {ROOTFS}/etc/resolv.conf")
    mounts = ["dev", "dev/pts", "proc", "sys", "run", "dev/shm"]
    for fs in mounts:
        target = f"{ROOTFS}/{fs}"
        run_as_sudo(f"mkdir -p {target}")
        run_as_sudo(f"mount --bind /{fs} {target} || true")

    subprocess.Popen("Xephyr :2 -screen 1280x720 -ac -br", shell=True)
    
    # Updated to login specifically as 'ubuntu'
    chroot_cmd = f"""
    sudo chroot {ROOTFS} /bin/bash -c '
        export DISPLAY=:2
        export XDG_RUNTIME_DIR=/tmp/runtime-ubuntu
        mkdir -p $XDG_RUNTIME_DIR && chmod 700 $XDG_RUNTIME_DIR
        chown -R ubuntu:ubuntu /home/ubuntu
        sudo -u ubuntu -i dbus-run-session -- startxfce4
    '
    """
    subprocess.Popen(chroot_cmd, shell=True)

def build_iso():
    try:
        # --- THE FIX: SYNC USER SETTINGS TO SKELETON ---
        print("Freezing Chicago95 settings into system template...")
        # Copy home config to etc/skel so Casper uses it as the default
        run_as_sudo(f"mkdir -p {ROOTFS}/etc/skel/.config")
        run_as_sudo(f"cp -r {ROOTFS}/home/ubuntu/.config/* {ROOTFS}/etc/skel/.config/ || true")
        
        # Ensure theme/icons are in global directories so they are accessible to all
        run_as_sudo(f"mkdir -p {ROOTFS}/usr/share/themes {ROOTFS}/usr/share/icons")
        run_as_sudo(f"cp -r {ROOTFS}/home/ubuntu/.themes/* {ROOTFS}/usr/share/themes/ || true")
        run_as_sudo(f"cp -r {ROOTFS}/home/ubuntu/.icons/* {ROOTFS}/usr/share/icons/ || true")
        
        # Set permissions for the template
        run_as_sudo(f"chown -R root:root {ROOTFS}/etc/skel/")
        # -----------------------------------------------

        for fs in ["dev/pts", "dev/shm", "dev", "proc", "sys", "run"]:
            run_as_sudo(f"umount -lf {ROOTFS}/{fs} || true")
        
        run_as_sudo(f"rm -rf {ISO_STAGING}")
        os.makedirs(os.path.join(ISO_STAGING, "casper"), exist_ok=True)
        run_as_sudo(f"mksquashfs {ROOTFS} {ISO_STAGING}/casper/filesystem.squashfs -comp xz")
        
        run_as_sudo(f"cp $(ls -v {ROOTFS}/boot/vmlinuz-* | tail -1) {ISO_STAGING}/casper/vmlinuz")
        run_as_sudo(f"cp $(ls -v {ROOTFS}/boot/initrd.img-* | tail -1) {ISO_STAGING}/casper/initrd")
        
        os.makedirs(os.path.join(ISO_STAGING, "boot/grub"), exist_ok=True)
        grub_conf = "set default=0\nset timeout=1\nmenuentry 'Chicago95 Ubuntu' { linux /casper/vmlinuz boot=casper quiet splash --- \n initrd /casper/initrd \n }"
        with open("temp_grub.cfg", "w") as f: f.write(grub_conf)
        run_as_sudo(f"mv temp_grub.cfg {ISO_STAGING}/boot/grub/grub.cfg")
        
        run_as_sudo(f"grub-mkrescue -o {OUTPUT_ISO} {ISO_STAGING}")
        messagebox.showinfo("Done", f"ISO built at {OUTPUT_ISO}")
    except Exception as e:
        messagebox.showerror("Build Error", str(e))

def launch_qemu():
    qemu_cmd = f"qemu-system-x86_64 -enable-kvm -m 4G -cdrom {OUTPUT_ISO} -vga virtio -display gtk,zoom-to-fit=on"
    subprocess.Popen(qemu_cmd, shell=True)

root = tk.Tk()
root.title("Chicago95 Builder")
tk.Button(root, text="1. Bootstrap", command=bootstrap_system).pack(fill="x")
tk.Button(root, text="2. Customize (Login as Ubuntu)", command=gui_chroot).pack(fill="x")
tk.Button(root, text="3. Build ISO (Auto-Sync)", command=build_iso).pack(fill="x")
tk.Button(root, text="4. Test", command=launch_qemu, bg="green", fg="white").pack(fill="x")
root.mainloop()
