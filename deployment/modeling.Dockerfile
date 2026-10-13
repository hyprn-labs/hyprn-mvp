# No install or network fetch: audited installed Ruby gems/native sources only.
ARG SOURCE_IMAGE
ARG RUBY_IMAGE
FROM ${SOURCE_IMAGE} AS source
USER root
WORKDIR /native
# Retained files of patches 010-040, replayed from the pinned upstream archive and the ordered
# patches (deployment/modeling_runtime.py); each replayed migration replaces the source
# image's migration of the same version.
RUN rm -f /native/db/migrate/20261008160000_*.rb /native/db/migrate/20261008175500_*.rb
COPY replay /native/
COPY native.patch /tmp/native.patch
RUN patch --batch --fuzz=0 -p1 < /tmp/native.patch
COPY discovery.patch /tmp/discovery.patch
RUN patch --batch --fuzz=0 -p1 < /tmp/discovery.patch
COPY assumptions.patch /tmp/assumptions.patch
RUN patch --batch --fuzz=0 -p1 < /tmp/assumptions.patch
COPY units.patch /tmp/units.patch
RUN patch --batch --fuzz=0 -p1 < /tmp/units.patch
# The cumulative 040-090 adapter is staged once; 090 has no native or generator hunks.
COPY modeling_contract.rb /native/app/services/modeling_contract.rb
COPY modeling.schema.json /native/config/modeling.schema.json
COPY provenance-inputs /native/provenance-inputs
COPY modeling_policy.rb /modeling_policy.rb
RUN ruby /modeling_policy.rb --install

FROM ${RUBY_IMAGE}
COPY --from=source /usr/local/bundle /usr/local/bundle
COPY --from=source /usr/local/bin/node /usr/local/bin/node
COPY --from=source /native /native
COPY start.sh /modeling-start.sh
COPY notices /usr/share/hyprn-mvp-modeling-source
RUN rm -f /usr/bin/python /usr/bin/python3 /usr/bin/python3.11 && mkdir -p /store /run /native/tmp /native/log && chmod 755 /modeling-start.sh && chown -R 10001:10001 /native/tmp /native/log
ENV RAILS_ENV=test BUNDLE_WITHOUT=production:staging BUNDLE_FROZEN=true HOME=/tmp DISABLE_BOOTSNAP=1 MODEL_KEY_FILE=/run/model.key
WORKDIR /native
USER 10001:10001
EXPOSE 3000
ENTRYPOINT ["sh", "/modeling-start.sh"]
