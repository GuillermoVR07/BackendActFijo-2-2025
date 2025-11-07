# api/db_router.py

class AnalyticsRouter:
    """
    Un router para controlar todas las operaciones de la base de datos para
    los modelos de Log (log_saas) y Predicciones (analytics_saas).
    El resto de modelos irá a 'default' (af_saas).
    """
    
    # Lista de modelos que irán a la base de datos 'log_saas'
    log_models = {'log'} # Nombres de modelos en minúscula
    
    # Lista de modelos que irán a la base de datos 'analytics_saas'
    analytics_models = {'prediccionmantenimiento', 'prediccionpresupuesto'}

    def db_for_read(self, model, **hints):
        model_name = model._meta.model_name
        if model_name in self.log_models:
            return 'log_saas'
        if model_name in self.analytics_models:
            return 'analytics_saas'
        # El resto va a 'default'
        return 'default'

    def db_for_write(self, model, **hints):
        model_name = model._meta.model_name
        if model_name in self.log_models:
            return 'log_saas'
        if model_name in self.analytics_models:
            return 'analytics_saas'
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """
        Permitir relaciones bajo condiciones específicas:
        1. Si ambos objetos pertenecen a la misma base de datos destino.
        2. Permitir explícitamente la relación entre Log (log_saas) y User (default).
        """
        db1 = self.db_for_read(obj1.__class__)
        db2 = self.db_for_read(obj2.__class__)
        app_label1 = obj1._meta.app_label
        app_label2 = obj2._meta.app_label
        model_name1 = obj1._meta.model_name
        model_name2 = obj2._meta.model_name

        # 1. Permitir si ambos objetos van a la misma BD
        if db1 == db2:
            return True

        # 2. Permitir explícitamente Log(log_saas) <-> User(default)
        # Verificamos los nombres de modelos Y las bases de datos destino
        is_log_user_relation = (
            (app_label1 == 'api' and model_name1 == 'log' and db1 == 'log_saas' and
             app_label2 == 'auth' and model_name2 == 'user' and db2 == 'default') or
            (app_label2 == 'api' and model_name2 == 'log' and db2 == 'log_saas' and
             app_label1 == 'auth' and model_name1 == 'user' and db1 == 'default')
        )

        if is_log_user_relation:
            # print(f"DEBUG Router: Allowing Log <-> User relation between {db1} and {db2}")
            return True # Permitir esta relación específica

        # Devolver None para otras relaciones cruzadas deja que Django decida
        # (Generalmente las previene si no son el caso Log->User que acabamos de permitir)
        # print(f"DEBUG Router: Defaulting relation check between {app_label1}.{model_name1}({db1}) and {app_label2}.{model_name2}({db2})")
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Asegurarse de que los modelos de log y analytics solo se migren
        a sus bases de datos correctas.
        """
        if db == 'log_saas':
            return model_name in self.log_models
        if db == 'analytics_saas':
            return model_name in self.analytics_models
        
        # Asegúrate de que los modelos de logs/analytics NO se migren a 'default'
        if db == 'default':
            return model_name not in self.log_models and model_name not in self.analytics_models
            
        return None