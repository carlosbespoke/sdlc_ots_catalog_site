go-diskfs cannot make crash-recoverable FAT metadata changes on whole disks or numbered partitions. Implement transactions for FAT12, FAT16, and FAT32 so committed mutations survive reopening completely, while rollback or interruption restores the prior coherent filesystem state. Make filesystem tree copying publish one recoverable destination outcome without changing established successful-copy behavior.

Rollback or interruption restores every touched allocation entry exactly, and overlapping transactions on one filesystem cannot publish conflicting outcomes or displace the active transaction. Reject unrepresentable clusters and values without writing bytes, and make durable state authoritative before reporting success. Include file, directory, allocation-chain, mirrored-table, and FAT32 free-space metadata in one outcome. Keep FAT12 and FAT16 fixed-root behavior without FSInformationSector writes.

Make recovery idempotent. Validate records against the selected filesystem geometry, never touch neighboring bytes, and return a coherent view before disk opening completes. Preserve existing probing errors, rename matching and replacement behavior, copy exclusions, contents, structure, timestamp handling, and label handling: an ordinary SetLabel made outside any transaction stays durable after the image is reopened. Keep existing exported signatures and concrete return types unchanged; in particular FileSystem.OpenFile continues to return a concrete *fat12.File.

Atomic copying must expose the complete reachable destination tree after reopening through Disk.GetFilesystem, or restore exactly the preceding tree after any source or destination failure. Nested directories and files must commit as one reachable tree.

Package github.com/diskfs/go-diskfs/filesystem/fat12 exports TransactionState, FATTransaction, ErrTransactionActive, RecoveryDisposition, and RecoveryReport; ErrTransactionActive reports exactly "FAT transaction already active". Package github.com/diskfs/go-diskfs/disk exposes Disk.RecoverFAT, and github.com/diskfs/go-diskfs/sync exposes CopyTransactionResult and CopyFileSystemAtomic. Disk.RecoverFAT returns an error, and writes no bytes, when the selected whole disk or partition holds no recognized FAT filesystem.

A FAT12 transaction spanning adjacent packed entries must reopen with byte-exact rollback or identical committed mirrored tables after durable synchronization. Interrupted file growth must restore the prior contents, length, allocation chain, and mirror agreement. Reject a malformed FAT32 transaction for incompatible partition geometry before changing reserved entries or neighboring partition bytes. Interrupted FAT32 commit recovery must leave allocation entries and FSInformationSector free-space hints describing the same durable outcome.

These are required in what you deliver:

- TransactionState: TransactionActive = iota, TransactionCommitted, TransactionRolledBack
- FATTransaction: SetCluster(cluster uint32, value uint32) error; Commit() error; Rollback() error; State() TransactionState
- (fs *FileSystem) BeginFATTransaction() (FATTransaction, error)
- (fs *FileSystem) RecoverFATTransaction() (RecoveryReport, error)
- ErrTransactionActive = errors.New("FAT transaction already active")
- RecoveryDisposition: RecoveryNone = iota, RecoveryRolledBack, RecoveryCompleted
- RecoveryReport{Disposition RecoveryDisposition}
- (d *Disk) RecoverFAT(partition int) (fat12.RecoveryReport, error)
- CopyTransactionResult{State fat12.TransactionState}
- CopyFileSystemAtomic(src fs.FS, dst *fat12.FileSystem) (CopyTransactionResult, error)


