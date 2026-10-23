# Progress

A wrapper around the native indeterminate progress element, used for queued, prepared, starting and running execution. The label states the observed stage; no percentage or remaining time is invented. Status changes are announced politely. Completion removes the track and reveals the run's results; execution completion never means criteria met or scientific validity. An uncertain outcome uses an explicit warning, not a running track. Automatic refreshes are read requests only.

An optional explicit `count` supplies completed/total work for sample points or assessed
groups. Only valid finite integer counts produce a determinate track. The label names
what is counted; it never represents overall elapsed time or scientific validity.


Recoverable interruptions use the warning “Paused” state and one primary Resume
action beside the explanation. Offer Resume only when the owner reports it is
allowed; never infer authority from an error's wording. A terminal failure with no
recovery remains Failed. Resume preserves saved work; it is distinct from Launch
and from changing a saved version. Disable the action while sending or reconciling
an uncertain command. Cancelled and Needs review are not running progress states.
