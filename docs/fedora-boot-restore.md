# Fedora Boot Backup Restore Guide

This guide explains how to restore a backup created by the `fedora-boot-backup` mise task.

The backup is useful when `/boot`, `/boot/efi`, GRUB, shim, EFI files, or UEFI boot entries are damaged. It is not a full system backup. In this setup, `/` is assumed to be protected separately by Snapper snapshots.

## Backup Layout

The task creates a directory like this:

```text
$HOME/boot-backup-YYYY-MM-DD/
├── boot/
│   ├── efi/
│   ├── grub2/
│   ├── loader/
│   ├── vmlinuz-*
│   └── initramfs-*.img
├── efibootmgr.txt
├── findmnt.txt
└── lsblk.txt
```

Use these files during recovery:

| File | Purpose |
| --- | --- |
| `boot/` | File backup of `/boot`, including `/boot/efi` if it was mounted when the task ran. |
| `lsblk.txt` | Shows the original block devices, filesystems, labels, and UUIDs. |
| `findmnt.txt` | Shows how `/boot` and `/boot/efi` were mounted. |
| `efibootmgr.txt` | Shows the original UEFI boot entries. Use it as a reference, not as an import file. |

## When To Use This

Use this restore process if the Fedora system itself is still recoverable, but boot files are missing or broken.

Common cases include:

1. `/boot` was accidentally deleted or overwritten.
2. `/boot/efi/EFI/fedora` was damaged.
3. GRUB, shim, or EFI files were replaced by another operating system.
4. A kernel, bootloader, or firmware update left the machine unbootable.
5. UEFI NVRAM boot entries were lost and need to be recreated.

## Preparation

Boot from a Fedora Live USB or another trusted Linux recovery environment.

Make sure the backup directory is available. It can be on an external drive, another internal partition, or copied into the live environment.

In the examples below, replace these placeholders:

| Placeholder | Meaning |
| --- | --- |
| `/path/to/boot-backup-YYYY-MM-DD` | The backup directory created by `fedora-boot-backup`. |
| `/dev/root-partition` | The Fedora root filesystem device. |
| `/dev/boot-partition` | The Fedora `/boot` partition. |
| `/dev/efi-partition` | The EFI System Partition. |
| `/dev/disk` | The whole disk that contains the EFI System Partition, for example `/dev/nvme0n1` or `/dev/sda`. |
| `N` | The EFI System Partition number on `/dev/disk`. |

Use the backup metadata to identify the right devices:

```bash
cat /path/to/boot-backup-YYYY-MM-DD/lsblk.txt
cat /path/to/boot-backup-YYYY-MM-DD/findmnt.txt
cat /path/to/boot-backup-YYYY-MM-DD/efibootmgr.txt
```

You can also inspect the live system:

```bash
lsblk -f
sudo findmnt
```

## Mount The Installed System

Mount the installed Fedora system under `/mnt`.

If your root filesystem is managed by Snapper, mount the root subvolume you want to repair or roll back to. The exact subvolume name depends on your layout, so use your existing Snapper and Btrfs setup as the source of truth.

Example without a custom Btrfs subvolume option:

```bash
sudo mount /dev/root-partition /mnt
```

Example with a Btrfs subvolume:

```bash
sudo mount -o subvol=@ /dev/root-partition /mnt
```

Mount `/boot` and `/boot/efi` into the installed system:

```bash
sudo mount /dev/boot-partition /mnt/boot
sudo mount /dev/efi-partition /mnt/boot/efi
```

Verify that the mounts are correct before copying anything:

```bash
findmnt /mnt
findmnt /mnt/boot
findmnt /mnt/boot/efi
```

Do not continue if `/mnt/boot/efi` is not a real EFI System Partition mount. If it is only an ordinary directory, the EFI files will be copied to the wrong place.

## Restore The Files

Set a shell variable for the backup path:

```bash
backup=/path/to/boot-backup-YYYY-MM-DD
```

Run a dry run first:

```bash
sudo rsync -aHAX --numeric-ids --delete --dry-run --exclude /efi/ "$backup/boot/" /mnt/boot/
sudo rsync -a --delete --dry-run "$backup/boot/efi/" /mnt/boot/efi/
```

If the dry run looks correct, restore `/boot` and `/boot/efi`:

```bash
sudo rsync -aHAX --numeric-ids --delete --exclude /efi/ "$backup/boot/" /mnt/boot/
sudo rsync -a --delete "$backup/boot/efi/" /mnt/boot/efi/
```

The restore is split into two commands because `/boot/efi` is usually a FAT filesystem. FAT does not support the same Linux ownership, ACL, and extended attribute behavior as a normal Linux filesystem, so restoring it with plain `rsync -a` is safer.

## Rebuild GRUB Configuration

Bind mount the runtime filesystems and enter the installed system:

```bash
sudo mount --bind /dev /mnt/dev
sudo mount --bind /proc /mnt/proc
sudo mount --bind /sys /mnt/sys
sudo mount --bind /run /mnt/run
sudo chroot /mnt
```

Rebuild Fedora's GRUB configuration:

```bash
grub2-mkconfig -o /boot/grub2/grub.cfg
```

If bootloader packages may be damaged, reinstall them from inside the chroot:

```bash
dnf reinstall shim-x64 grub2-efi-x64 grub2-tools
grub2-mkconfig -o /boot/grub2/grub.cfg
```

Exit the chroot:

```bash
exit
```

## Recreate The UEFI Boot Entry If Needed

If the firmware no longer shows a Fedora boot entry, recreate it with `efibootmgr`.

First confirm the loader path exists:

```bash
ls /mnt/boot/efi/EFI/fedora/
```

For a normal Fedora Secure Boot setup, the loader is usually `\EFI\fedora\shimx64.efi`.

Create the boot entry:

```bash
sudo efibootmgr --create --disk /dev/disk --part N --label "Fedora" --loader '\EFI\fedora\shimx64.efi'
```

If Secure Boot is disabled and you intentionally boot GRUB directly, the loader may be:

```text
\EFI\fedora\grubx64.efi
```

Check the restored files and the old `efibootmgr.txt` before choosing the loader path.

Verify the new boot entry:

```bash
sudo efibootmgr -v
```

## Unmount And Reboot

Flush pending writes:

```bash
sync
```

Unmount in reverse order:

```bash
sudo umount /mnt/run
sudo umount /mnt/sys
sudo umount /mnt/proc
sudo umount /mnt/dev
sudo umount /mnt/boot/efi
sudo umount /mnt/boot
sudo umount /mnt
```

Reboot:

```bash
sudo reboot
```

## After Booting Successfully

Once Fedora boots again, verify the current state:

```bash
findmnt /boot /boot/efi
lsblk -f
sudo efibootmgr -v
sudo grub2-mkconfig -o /boot/grub2/grub.cfg
```

Then create a fresh backup:

```bash
mise run fedora-boot-backup
```

## Notes

Do not blindly reuse disk names from examples. Always use `lsblk.txt`, `findmnt.txt`, and the current `lsblk -f` output.

Do not copy EFI files before mounting `/mnt/boot/efi`.

Do not treat `efibootmgr.txt` as something that can be imported. UEFI entries point to a specific disk and partition, so they should be recreated for the current machine state.

If Snapper is used to roll back `/`, complete the Snapper rollback first, then mount the resulting root state and restore `/boot` and `/boot/efi` so the kernel, initramfs, GRUB configuration, and root snapshot agree with each other.
