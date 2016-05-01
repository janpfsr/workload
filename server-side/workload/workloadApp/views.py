"""
The Django view functions for the Website

The workload project provides a public-facing website which can be used by the students to enter
their data. This file contains the view functions that make up the website. It uses the same
models as the the view functions of the API, which are located in the api_views.py file.

Above the view functions, this file also contains a number of relevant helpter functions.
"""

from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext, loader
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import Group
from django.utils.decorators import method_decorator
from django.views.decorators.cache import patch_cache_control
from objects import Week, Semester
from datetime import date, timedelta
from workloadApp.models import WorkingHoursEntry, Lecture, Student
from functools import wraps
from copy import deepcopy



#Helper functions

def privacy_agreement(user):
    """ Checks if user belongs to the group of users which have agreed to the privacy agreement"""
    if user:
        return user.groups.filter(name='has_agreed_to_privacy_agreement').exists()
    return False


def decorateWithNotification(request):
    """ This method allows to show the user a notification based on a POST or GET parameter

    Unfortunately only a single notification per request is supported. It must be passed with key
    "notification" in the GET or POST dictionary. 
    """
    params = dict(list(request.GET.items()) + list(request.POST.items()))
    if "notification" in params:
        return {"hasNotification" : True , "notification" : params["notification"]}
    else:
        return {"hasNotification" : False}


def never_ever_cache(decorated_function):
    """Like Django @never_cache but sets more valid cache disabling headers.

    @never_cache only sets Cache-Control:max-age=0 which is not
    enough. For example, with max-axe=0 Firefox returns cached results
    of GET calls when it is restarted.
    """
    @wraps(decorated_function)
    def wrapper(*args, **kwargs):
        response = decorated_function(*args, **kwargs)
        patch_cache_control(
            response, no_cache=True, no_store=True, must_revalidate=True,
            max_age=0)
        return response
    return wrapper

def wrap(context, request):
    """ Updates the context dictionary with the notification information and test account info """
    context.update(decorateWithNotification(request))
    context.update({ "ignoreData" : request.user.student.ignoreData })
    return context



@login_required
@user_passes_test(privacy_agreement, login_url='/app/workload/privacyAgreement/?notification=Please confirm the privacy policy.')
@method_decorator(never_ever_cache) 
# Apparently since I added never_ever_cache this here, 
# the other views seem to be updating nicely as well. Coincidence?
def calendar(request):
    weeks = request.user.student.getWeeks()
    context = RequestContext(request, {
        "semesters" : Semester.groupWeeksBySemester(weeks)
    })
    template = loader.get_template('workloadApp/calendar.html')
    return HttpResponse(template.render(wrap(context, request)))



@login_required
@user_passes_test(privacy_agreement, login_url='/app/workload/privacyAgreement/?notification=Please confirm the privacy policy.')
def selectLecture(request):
    student = request.user.student
    weekNumber = int(request.GET['week'])
    yearNumber = int(request.GET['year'])
    week = Week(yearNumber, weekNumber)

    template = loader.get_template('workloadApp/selectLecture.html')
    
    lecturesThisWeek = student.getLectures(week)
    lectureHasData = [ True if WorkingHoursEntry.objects.filter(week=week.monday(), student=student,lecture=lecture) else False for lecture in lecturesThisWeek]

    context = RequestContext(request, {
        "year" : yearNumber,
        "week" : weekNumber,
        "lecturesToDisplay" : zip(lecturesThisWeek, lectureHasData)
    })
    return HttpResponse(template.render(wrap(context, request)))

@login_required
@user_passes_test(privacy_agreement, login_url='/app/workload/privacyAgreement/?notification=Please confirm the privacy policy.')
def enterWorkloadData(request):

    week = Week(int(request.GET['year']),int(request.GET['week'])) # create isoweek object
    lecture = Lecture.objects.get(id=int(request.GET['lectureId'])) 
    dataEntry, hasBeenCreated = WorkingHoursEntry.objects.get_or_create( week=week.monday() , student=request.user.student , lecture=lecture)

    template = loader.get_template('workloadApp/enterWorkloadData.html')

    context = RequestContext(request,{
        "week" : week,
        "lecture" : lecture,
        # it is probably smarter to simply return the full dataEntry object
        "hoursInLecture" : dataEntry.hoursInLecture,
        "hoursForHomework" : dataEntry.hoursForHomework,
        "hoursStudying" : dataEntry.hoursStudying,
    })
    return HttpResponse(template.render(wrap(context, request)))

@login_required
@user_passes_test(privacy_agreement, login_url='/app/workload/privacyAgreement/?notification=Please confirm the privacy policy.')
def postWorkloadDataEntry(request):
    #TODO: Make sure ALL post variables are set

    year = int(request.POST['year'])
    lecture = Lecture.objects.get(id=request.POST['lectureId'])
    dataEntry, hasBeenCreated = WorkingHoursEntry.objects.get_or_create( week=Week(int(request.POST['year']),int(request.POST['week'])).monday() , student=request.user.student , lecture=lecture)
    dataEntry.hoursInLecture   = float(request.POST["hoursInLecture"])
    dataEntry.hoursForHomework = float(request.POST["hoursForHomework"])
    dataEntry.hoursStudying    = float(request.POST["hoursStudying"])
    dataEntry.semesterOfStudy = request.user.student.semesterOfStudy # the semester of study of the student at the time when the dataEntry is created
    dataEntry.save()
    return HttpResponse("success")


@login_required
@user_passes_test(privacy_agreement, login_url='/app/workload/privacyAgreement/?notification=Please confirm the privacy policy.')
def addLecture(request):

    # Here the student can choose the list of lectures for which he wants to collect data
    #lectures are sorted by semester

    # If the reach of the application is extended, one can introduce greater hirachies here
    #if "studies" in request.GET.keys():
    #    # Can be "Master Physik" or "Bachelor Physik"

    context = RequestContext(request,{})
    if "semester" in request.GET.keys():
        template = loader.get_template('workloadApp/addLecture/choose.html')
        context.update({"lectures" : Lecture.objects.filter(semester=request.GET["semester"]).exclude(student=request.user.student)})
    else:
        template = loader.get_template('workloadApp/addLecture/selectSemester.html')
        context.update({"allSemesters" : Lecture.objects.all().values_list("semester", flat=True).distinct()})
    return HttpResponse(template.render(wrap(context, request)))

@login_required
@user_passes_test(privacy_agreement, login_url='/app/workload/privacyAgreement/?notification=Please confirm the privacy policy.')
def options(request):
    template = loader.get_template('workloadApp/options.html')
    context = RequestContext(request, {})
    return HttpResponse(template.render(wrap(context, request)))

@login_required
@user_passes_test(privacy_agreement, login_url='/app/workload/privacyAgreement/?notification=Please confirm the privacy policy.')
def settings(request):
    template = loader.get_template('workloadApp/options/settings.html')
    context = RequestContext(request,{
        "studentID" : request.user.student.id,
        "semesterOfStudy" : request.user.student.semesterOfStudy
        })
    return HttpResponse(template.render(wrap(context, request)))

@login_required
@user_passes_test(privacy_agreement, login_url='/app/workload/privacyAgreement/?notification=Please confirm the privacy policy.')
def permanentDelete(request):
    template = loader.get_template('workloadApp/options/settings/permanentDelete.html')

    context = RequestContext(request,{
        "allLectures" : list(set(Lecture.objects.filter(workinghoursentry__student=request.user.student)))
        })
    context.update(decorateWithNotification(request))
    context.update({ "ignoreData" : request.user.student.ignoreData })
    return HttpResponse(template.render(context))

@login_required
def doPermanentDelete(request):
    lectureToRemove = Lecture.objects.get(id=request.POST["lectureId"])
    request.user.student.lectures.remove(lectureToRemove)
    WorkingHoursEntry.objects.filter(lecture__id=request.POST["lectureId"],student=request.user.student).delete()
    return HttpResponse("success")




@login_required
@user_passes_test(privacy_agreement, login_url='/app/workload/privacyAgreement/?notification=Please confirm the privacy policy.')
def chosenLectures(request):
    
    if "lectureId" in request.GET: # TODO: Move this function into API. use ajax post for this
        lectureToRemove = Lecture.objects.get(id=request.GET["lectureId"])
        request.user.student.lectures.remove(lectureToRemove)
        return HttpResponseRedirect("/app/workload/options/chosenLectures/?notification=Lecture removed from list")

     # TODO: Move this function into API. Somehow use ajax post for this
    if "addLecture" in request.GET.keys():
        lecture = Lecture.objects.get(pk=request.GET["addLecture"])
        request.user.student.lectures.add(lecture)
        request.user.student.save()


    template = loader.get_template('workloadApp/options/chosenLectures.html')    

    context = RequestContext(request,
                             {"chosenLectures" : list(request.user.student.lectures.all())})
    return HttpResponse(template.render(wrap(context, request)))

def logoutView(request):
    #this is pretty broken and probably does not work with shibboleth
    logout(request)
    return HttpResponseRedirect("/app/workload/?notification=You have been logged out.")


@login_required
# here, agreemetn to the privacy agreement is obviously not required
def privacyAgreement(request):

    if request.method =="POST":  #the user has responed to the form
        if "privacy" in request.POST:
            g = Group.objects.get(name='has_agreed_to_privacy_agreement')
            g.user_set.add(request.user)
            return HttpResponseRedirect("/app/workload/calendar?notification=You have agreed to the privacy agreement")
        else:
            return HttpResponseRedirect("./?notification=You must check the checkbox.")


    template = loader.get_template('workloadApp/privacyAgreement.html')
    context = RequestContext(request,{ # it would be a good idea to pass here the users insitution
         "has_agreed_to_privacy_agreement" : privacy_agreement(request.user)
        })
    return HttpResponse(template.render(wrap(context, request)))



@login_required
@user_passes_test(privacy_agreement, login_url='/app/workload/privacyAgreement/?notification=Please confirm the privacy policy.')
def visualizeData(request):
    student = request.user.student

    #gathering data for first diagram
    weeks = student.getWeeks()
    weekData = []
    for lecture in student.lectures.all():
        dictionary = { "name": lecture.name, "data":[]} 
        for week in weeks:
            try:
                hours = WorkingHoursEntry.objects.get(week=week.monday(),student=request.user.student,lecture=lecture).getTotalHours()
            except WorkingHoursEntry.DoesNotExist:
                hours = 0
            dictionary["data"].append(hours)
        weekData.append(dictionary)

    diagram1 = {
        "categories" : [week.monday().strftime('%b') for week in weeks],
        "series" : weekData
    }

    # #gathering data for second diagram

    categories = student.lectures.all()
    series = [
        {"name": "attending", "data": [student.getHoursSpent(lecture)["inLecture"] for lecture in categories] }, 
        {"name": "homework" , "data": [student.getHoursSpent(lecture)["forHomework"] for lecture in categories]},
        {"name": "studies"  , "data": [student.getHoursSpent(lecture)["studying"] for lecture in categories]}]

    diagram2={
        "categories" :  [lecture.name for lecture in categories], #hack to prevent a crash
        "series" : series
    }
   
    template = loader.get_template('workloadApp/visualizeData.html')

    #gathering data for first pie chart
    totalhours = deepcopy(series) # we re-use what we collected above
    for activity in totalhours:
        activity["y"] = sum(activity["data"])
        activity.pop("data")

    #gathering data for second pie chart
    pie2 = [{"name" : lecture.name, "y" : sum(student.getHoursSpent(lecture).values())} for lecture in student.lectures.all()]


    context = RequestContext(request,{
        "diagram1" : diagram1,
        "diagram2" : diagram2,
        "pie1" : totalhours,
        "pie2" : pie2

        })

    return HttpResponse(template.render(wrap(context, request)))



