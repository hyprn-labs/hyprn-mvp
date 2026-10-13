# SPDX-License-Identifier: AGPL-3.0-only
# Native deployment adaptation; retain together with WhatsOpt corresponding source.
require 'fileutils'
if ARGV == ['--install']
  root = '/native'
  %w[node_modules .yarn .git public app/javascript app/views app/assets app/helpers app/jobs app/channels app/mailers lib test spec storage log tmp].each { |p| FileUtils.rm_rf("#{root}/#{p}") }
  Dir.glob("#{root}/app/controllers/*").each { |p| FileUtils.rm_rf(p) unless File.basename(p) == 'modeling_contract_controller.rb' }
  # Services: only the contract adapter and the native static producer remain; any other
  # service of the source image (an earlier authoring service among them) is removed.
  allowed_services = %w[modeling_contract.rb native_materializer.rb native_program.rb native_provenance.rb]
  Dir.glob("#{root}/app/services/*", File::FNM_DOTMATCH).each do |path|
    next if %w[. ..].include?(File.basename(path)) || allowed_services.include?(File.basename(path))
    FileUtils.rm_rf(path)
  end
  # Retain only the separately patched static generator closure; execution helpers stay removed.
  %w[salib_sensitivity_analyser server_generator egmdo_generator gemseo_generator].each { |n| FileUtils.rm_f("#{root}/app/lib/whats_opt/#{n}.rb") }
  allowed_templates = %w[openmdao_analysis.py.erb openmdao_analysis_base.py.erb openmdao_discipline.py.erb openmdao_discipline_base.py.erb base_header_partial.py.erb __init__.py.erb]
  Dir.glob("#{root}/app/lib/whats_opt/templates/*", File::FNM_DOTMATCH).each do |path|
    next if %w[. ..].include?(File.basename(path)) || allowed_templates.include?(File.basename(path))
    FileUtils.rm_rf(path)
  end
  raise 'Native static patch must precede policy installation' unless File.read("#{root}/app/lib/whats_opt/openmdao_generator.rb").include?('static_only: false')
  %w[log tmp/cache tmp/pids lib/tasks app/assets/config].each { |p| FileUtils.mkdir_p("#{root}/#{p}") }
  File.write("#{root}/app/assets/config/manifest.js", '')
  File.write("#{root}/config/routes.rb", "Rails.application.routes.draw do\n  match '/modeling/1/*contract_path', to: 'modeling_contract#dispatch_contract', via: [:get, :post]\nend\n")
  File.write("#{root}/config/database.yml", "test:\n  primary:\n    adapter: sqlite3\n    database: /store/model.sqlite3\n    timeout: 10000\n  scratch:\n    adapter: sqlite3\n    database: /store/scratch.sqlite3\n    migrations_paths: db/scratch_migrate\n")
  File.write("#{root}/config/configuration.yml", "test:\n  enable_ldap: false\n  restrict_access: true\n  python_cmd: /bin/false\n  thrift_cmd: /bin/false\n")
  File.write("#{root}/config/environments/test.rb", <<~CONFIG)
    Rails.application.configure do
      config.enable_reloading = false
      config.eager_load = false
      config.consider_all_requests_local = false
      config.public_file_server.enabled = false
      config.action_dispatch.show_exceptions = :all
      config.cache_store = :null_store
      config.active_storage.service = :test
      config.action_mailer.delivery_method = :test
      config.active_job.queue_adapter = :inline
      config.active_record.dump_schema_after_migration = false
      config.logger = ActiveSupport::Logger.new($stdout)
      config.log_level = :warn
      config.secret_key_base = ENV['NATIVE_STATIC_GENERATION']=='1' ? ENV.fetch('SECRET_KEY_BASE') : File.read('/run/rails.key').strip
    end
  CONFIG
  # Native labels must never interpret display names as filesystem/module paths.
  service = "#{root}/app/services/modeling_contract.rb"
  text = File.read(service)
  old = "native=Analysis.create!(name:body['name'],public:false)"
  raise 'Unexpected adapter source' unless text.include?(old)
  File.write(service, text.sub(old, "native=Analysis.create!(name:'model_'+model_id.delete('-'),public:false)"))
  # Probe initializers of the source image and the controller renderer are removed.
  Dir.glob("#{root}/config/initializers/*_probe.rb").each { |path| FileUtils.rm_f(path) }
  FileUtils.rm_f("#{root}/config/initializers/application_controller_renderer.rb")
  # A first middleware rejects every non-contract path before Rails sessions/assets.
  File.write("#{root}/config/initializers/modeling_only.rb", <<~POLICY)
    class ModelingOnly
      def initialize(app) = @app=app
      def call(env)
        unless env['PATH_INFO'].start_with?('/modeling/1/') && ['GET','POST'].include?(env['REQUEST_METHOD'])
          return [404, {'content-type'=>'application/json'}, ['{"error":"not_found"}']]
        end
        @app.call(env)
      end
    end
    Rails.application.config.middleware.insert_before 0, ModelingOnly
  POLICY
else
  abort 'Build-time --install only'
end
