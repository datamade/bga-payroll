TMPDIR:=$(shell mktemp -d)
NAME=
EMAIL=
SERVER=
PROJECT=

define GPG_SETUP
%echo Generating a basic OpenPGP key\n
Key-Type: RSA\n
Key-Length: 4096\n
Key-Usage: sign\n
Subkey-Type: RSA\n
Subkey-Length: 4096\n
Subkey-Usage: encrypt\n
Name-Real: $(NAME)\n
Name-Email: $(EMAIL)\n
Expire-Date: 0\n
%commit\n
%echo done\n
endef

export GPG_SETUP

all : transfer indoctrinate

.INTERMEDIATE: gpg_setup
gpg_setup :
	echo $$GPG_SETUP > $@

$(TMPDIR)/pubring.gpg : gpg_setup
	gpg --homedir=$(TMPDIR) --batch --gen-key $<

$(TMPDIR)/private.key : $(TMPDIR)/pubring.gpg 
	gpg --homedir=$(TMPDIR) --export-secret-keys $(EMAIL) > $@

$(TMPDIR)/public.key : $(TMPDIR)/pubring.gpg 
	gpg --homedir=$(TMPDIR) --export -a $(EMAIL) > $@

transfer: $(TMPDIR)/private.key
	-ssh ubuntu@$(SERVER) 'sudo -u datamade mkdir -p /home/datamade/.gnupg/$(PROJECT)'
	rsync -a --rsync-path="sudo -u datamade rsync" $< ubuntu@$(SERVER):/home/datamade/.gnupg/$(PROJECT)
	ssh ubuntu@$(SERVER) 'sudo -u datamade -H gpg --import /home/datamade/.gnupg/$(PROJECT)/private.key'

indoctrinate : $(TMPDIR)/public.key
	blackbox_addadmin $(EMAIL) $(TMPDIR)
