# Progress

A wrapper around the native indeterminate progress element, used for queued, prepared, starting and running execution. The label states the observed stage; no percentage or remaining time is invented. Status changes are announced politely. Completion removes the track and reveals the run's results; execution completion never means criteria met or scientific validity. An uncertain outcome uses an explicit warning, not a running track. Automatic refreshes are read requests only.

An optional explicit `count` supplies completed/total work for sample points or assessed
groups. Only valid finite integer counts produce a determinate track. The label names
what is counted; it never represents overall elapsed time or scientific validity.
