from shibboleth.backends import ShibbolethRemoteUserBackend
from models import Student
from django.contrib.auth import get_user_model
import re
import logging
logger = logging.getLogger(__name__)


class CustomShibboBackend(ShibbolethRemoteUserBackend):

    def authenticate(self, remote_user, meta):
        if not remote_user:
            return
        user = None
        username = self.clean_username(remote_user)
        UserModel = get_user_model()

        user, created = UserModel._default_manager.get_or_create(**{
            UserModel.USERNAME_FIELD: username
        })
        if created:
            user = self.configure_user(user,meta)
        student , _ = Student.objects.get_or_create(user=user)
        # update student object on every load
        try:
            logger.info(meta)
            regex = re.compile("\$ (\d*)") #capturing the semester of study which seems to follow a number indicating the course of study and a $ sign.
            student.semesterOfStudy = int( regex.findall(meta["terms-of-study"])[0] )
        except KeyError:
            # if the study term is not defined, set it to zero
            student.semesterOfStudy = 0
        except ValueError:
            #unable to convert value to integer
            student.semesterOfStudy = 0
        student.save()
        return user

    def clean_username(self,value):
        # find relevant substring of shibboleth attribute
        regex = re.compile("de/shibboleth\!(.*)=")
        value = regex.findall(value)[-1]
        # remove special characters
        value = ''.join(e for e in value if e.isalnum())
        return value
