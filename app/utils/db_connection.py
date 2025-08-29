import psycopg2    
import psycopg2.extras

class dbmethods:    
    def connect_db(self,dct_tenant_data):
        
        """Database Connection
        """
        # dct_tenant_data={}
        # dct_tenant_data['db_name'] = 'nubot_test_2025'
        # dct_tenant_data['db_host'] = '192.168.3.188'
        # dct_tenant_data['db_port'] = '5432'
        # dct_tenant_data['db_user'] = 'admin'
        # dct_tenant_data['db_password'] = 'asdfgh'
        try:
            self.ins_db = psycopg2.connect("""dbname=%s user=%s password=%s host=%s port=%s"""%
                                                (dct_tenant_data['db_name'],
                                                dct_tenant_data['db_user'],
                                                dct_tenant_data['db_password'],
                                                dct_tenant_data['db_host'],
                                                dct_tenant_data['db_port']))
            
        except Exception as msg:
            print(msg)
            raise
        
        try:
            cr1 = self.create_cursor()
            cr1.execute("""SET datestyle = 'DMY'""")
        except Exception as msg:
            self.ins_db.rollback()
            cr1.close()
            raise
        else:
            cr1.close()
            self.ins_db.commit()
            return self.ins_db
            pass  

    def create_cursor(self,*args):
        cr = self.ins_db.cursor(cursor_factory=psycopg2.extras.DictCursor)
        return cr