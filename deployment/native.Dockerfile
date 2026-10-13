# Disposable native application build. Context is verified upstream source OFF CLOUD.
ARG RUBY_IMAGE
ARG NODE_IMAGE
FROM ${NODE_IMAGE} AS node
FROM ${RUBY_IMAGE}
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && ln -s /usr/local/lib/node_modules/corepack/dist/corepack.js /usr/local/bin/corepack
WORKDIR /native
COPY . .
ENV BUNDLE_WITHOUT=production:staging BUNDLE_FROZEN=true RAILS_ENV=development
RUN gem install bundler -v 2.7.1 --no-document && bundle install --jobs 4
RUN corepack enable && corepack prepare yarn@4.14.1 --activate && yarn install --immutable
EXPOSE 3000
CMD ["bundle", "exec", "rails", "server", "-b", "0.0.0.0"]
