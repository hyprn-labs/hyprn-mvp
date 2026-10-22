# Acquisition stage: the context contains only verified upstream bytes and the gem lock.
ARG RUBY_IMAGE
ARG NODE_IMAGE
FROM ${NODE_IMAGE} AS node
FROM ${RUBY_IMAGE}
ARG BUILD_INPUT_DIGEST
LABEL org.hyprn-mvp.modeling-source-inputs=$BUILD_INPUT_DIGEST
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && \
    ln -s /usr/local/lib/node_modules/corepack/dist/corepack.js /usr/local/bin/corepack
WORKDIR /native
COPY upstream/ ./
COPY whatsopt-gems.json /tmp/whatsopt-gems.json
ENV BUNDLE_WITHOUT=production:staging BUNDLE_FROZEN=true RAILS_ENV=development
RUN gem install bundler -v 2.7.1 --no-document && bundle install --jobs 4
# Refuse any unrecorded archive, missing archive or changed installed package download.
RUN ruby -rjson -rdigest -e 'pins=JSON.parse(File.read("/tmp/whatsopt-gems.json")).fetch("gems"); \
    arch={"aarch64-linux"=>"aarch64-linux-gnu","x86_64-linux"=>"x86_64-linux-gnu"}.fetch(RUBY_PLATFORM); \
    pins=pins.select { |g| ["ruby",arch].include?(g.fetch("platform")) }; \
    expected=pins.to_h { |g| [g.fetch("filename"),g.fetch("sha256")] }; \
    actual=Dir["/usr/local/bundle/cache/*.gem"].to_h { |p| [File.basename(p),Digest::SHA256.file(p).hexdigest] }; \
    abort "Gem archive identity mismatch" unless actual == expected'
RUN corepack enable && corepack prepare yarn@4.14.1 --activate && yarn install --immutable
EXPOSE 3000
CMD ["bundle", "exec", "rails", "server", "-b", "0.0.0.0"]
