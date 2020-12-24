from sqlalchemy import or_
from mindsdb.interfaces.state.schemas import session, Datasource, Predictor, Configuration, Semaphor, Log
from mindsdb.interfaces.state.storage import StorageEngine
import mindsdb_native
import json


class State():
    def __init__(self, config):
        self.storage = StorageEngine()
        self.config = config
        self.company_id = self.config['company_id']
        self.dbw = None

    def init_wrapper(self):
        from mindsdb.interfaces.database.database import DatabaseWrapper
        if self.dbw is None:
         self.dbw = DatabaseWrapper(self.config)

    # Predictors
    def make_predictor(self, name, datasource_id, to_predict):
        predictor = Predictor(name=name, datasource_id=datasource_id, native_version=mindsdb_native.__version__, to_predict=','.join(to_predict), company_id=self.company_id, status='training', data=None)
        session.add(predictor)
        session.commit()

    def update_predictor(self, name, status, original_path, data, to_predict=None):
        predictor = Predictor.query.filter_by(name=name, company_id=self.company_id, native_version=mindsdb_native.__version__).first()

        predictor.status = status
        predictor.data = data
        if to_predict is not None:
            predictor.to_predict = ','.join(to_predict)

        if self.storage.location != 'local':
            storage_path = f'predictor_{predictor.company_id}_{predictor.name}'
            predictor.storage_path = storage_path
            self.storage.put_fs_node(storage_path, original_path)
        session.commit()

        self.init_wrapper()
        try:
            self.dbw.register_predictors([{
                'name': predictor.name,
                'predict': predictor.to_predict.split(','),
                'data_analysis': json.loads(predictor.data)
            }], False)
        except Exception as e:
            print(e)

    def delete_predictor(self, name):
        predictor = Predictor.query.filter_by(name=name, company_id=self.company_id, native_version=mindsdb_native.__version__).first()
        storage_path = predictor.storage_path
        session.delete(predictor)
        session.commit()
        #self.populate_registrations()
        self.init_wrapper()
        self.dbw.unregister_predictor(name) #<--- broken, but this should be the way we do it

        if self.storage.location != 'local':
            self.storage.del_fs_node(storage_path)

    def get_predictor(self, name):
        predictor = Predictor.query.filter_by(name=name, company_id=self.company_id, native_version=mindsdb_native.__version__).first()
        return predictor

    def load_predictor(self, name):
        predictor = Predictor.query.filter_by(name=name, company_id=self.company_id, native_version=mindsdb_native.__version__).first()
        if self.storage.location != 'local':
            pass

    def list_predictors(self):
        return Predictor.query.filter_by(company_id=self.company_id, native_version=mindsdb_native.__version__)

    # Integrations
    def list_integrations(self):
        return Integration.query.filter_by(company_id=self.company_id, native_version=mindsdb_native.__version__)

    def populate_registrations(self):
        register_predictors = []
        for predictor in self.list_predictors():
            predictor_id = predictor.id
            if predictor.data is not None:
                register_predictors.append({
                    'name': predictor.name,
                    'predict': predictor.to_predict.split(','),
                    'data_analysis': json.loads(predictor.data)
                })
        self.init_wrapper()
        self.dbw.register_predictors(register_predictors, True)

    # Datasources
    def make_datasource(self, name, data, analysis, storage_path):
        if self.storage.location != 'local':
            storage_path = f'datasource_{datasource.company_id}_{predictor.name}'
        else:
            storage_path = 'local'

        datasource = Datasource(name=name, data=data, analysis=analysis, company_id=self.company_id, storage_path=storage_path)

        session.add(datasource)
        session.commit()

    def update_datasource(self, name, analysis):
        datasource = Datasource.query.filter_by(name=name, company_id=self.company_id).first()
        datasource.analysis = analysis
        session.commit()

    def delete_datasource(self, name):
        datasource = Datasource.query.filter_by(name=name, company_id=self.company_id).first()
        storage_path = datasource.storage_path
        session.delete(datasource)
        session.commit()
        if self.storage.location != 'local':
            # Delete from storage
            pass

    def get_datasource(self, name):
        datasource = Datasource.query.filter_by(name=name, company_id=self.company_id).first()
        return datasource

    def load_datasource(self, name):
        datasource = Datasource.query.filter_by(name=name, company_id=self.company_id).first()
        if self.storage.location != 'local':
            pass

    def list_datasources(self, as_dict=False):
        datasources = Datasource.query.filter_by(company_id=self.company_id)
        return datasources

    # Log
    def record_log(self, log_type, source, payload):
        log = Log(log_type=log_type, source=source, payload=payload, company_id=self.company_id)

        session.add(log)
        session.commit()

    def _log_to_json(self, log_record):
        return {
            'log_type': log_record.log_type
            ,'source': log_record.source
            ,'payload': log_record.payload
        }

    def latest_logs(self):
        return [self._log_to_json(x) for x in Log.query.filter_by(company_id=self.company_id).limit(50)]

    def latest_error_logs(self):
        return [self._log_to_json(x) for x in Log.query
                .filter(Log.company_id == self.company_id)
                .filter((Log.log_type == 'ERROR') | (Log.log_type == 'WARNING')).limit(50)]