all:
  children:
    admin:
      hosts:
        admin.%ZONE%:
    login:
      hosts:
        login.%ZONE%:
    compute:
      hosts:
        cn[1:2].%ZONE%:
  vars:
    fhpc_zone: %ZONE%
