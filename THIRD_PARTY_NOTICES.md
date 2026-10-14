# Third-party notices

HYPRN MVP keeps separate notices for each delivered component. The complete licensing inventory and unresolved legal items are in [Licensing](docs/legal/licensing.md).

| Component | Licence and source record | Shipped notices |
|---|---|---|
| WhatsOpt private modeling service and HYPRN MVP modeling patches | AGPL-3.0; exact upstream commit, archive hash and size in `deployment/locks/upstream.json` | Original upstream archive, licence, ordered patches, build recipes and locks in the modeling image's corresponding-source directory; `modeling/provenance.md` |
| Ruby gems used by WhatsOpt | Per-gem licences and verified download hashes in `deployment/locks/whatsopt-gems.json` | Gem licence files retained with the installed gem tree |
| Ruby, Node and container operating-system components | Digest-pinned bases in `deployment/pins.json`; upstream base-image notices | Notices retained from each base image |
| OpenMDAO and restricted-worker dependencies | Apache-2.0 and the audited dependency licences; `integration/provenance.md` | Installed package licence files and pinned worker lock |
| AiiDA and native host dependencies | MIT and the audited dependency licences; `docs/operations/dependency-audit.md` | Installed inventory and `licenses/native/` in the prepared native environment |
| Python application dependencies | Per-package licences in `application/provenance.md` | Installed package licence files and hashed application lock |
| React, React DOM and scheduler | MIT | `ui/public/THIRD_PARTY_NOTICES.txt`, served with the UI |

WhatsOpt product UI is not distributed. Generated model code remains within the recorded AGPL compliance scope pending legal review. Local-edition distribution and commercial cloud obligations remain pending under L1 and L4 in the licensing inventory.
