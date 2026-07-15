# Database policies

## Monitor ownership

Monitors are owned by exactly one user. Deleting a user deletes that user's monitors
and, through their foreign keys, all monitor execution history. This cascade is the
intentional account-deletion policy; monitors are not reassigned or retained as
ownerless records.
