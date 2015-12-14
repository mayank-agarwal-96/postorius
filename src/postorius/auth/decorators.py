# -*- coding: utf-8 -*-
# Copyright (C) 1998-2015 by the Free Software Foundation, Inc.
#
# This file is part of Postorius.
#
# Postorius is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# Postorius is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# Postorius.  If not, see <http://www.gnu.org/licenses/>.
"""Postorius view decorators."""


from django.contrib.auth import logout, authenticate, login
from django.core.exceptions import PermissionDenied

from postorius.models import (Domain, List, Member, MailmanUser,
                              MailmanApiError, Mailman404Error)
from postorius.utils import user_is_in_list_roster


def basic_auth_login(fn):
    def wrapper(*args, **kwargs):
        request = args[0]
        if request.user.is_authenticated():
            print('already logged in')
        if not request.user.is_authenticated():
            if request.META.has_key('HTTP_AUTHORIZATION'):
                authmeth, auth = request.META['HTTP_AUTHORIZATION'].split(' ',
                                                                          1)
                if authmeth.lower() == 'basic':
                    auth = auth.strip().decode('base64')
                    username, password = auth.split(':', 1)
                    user = authenticate(username=username, password=password)
                    if user:
                        login(request, user)
        return fn(request, **kwargs)
    return wrapper


def list_owner_required(fn):
    """Check if the logged in user is the list owner of the given list.
    Assumes that the request object is the first arg and that list_id
    is present in kwargs.
    """
    def wrapper(*args, **kwargs):
        user = args[0].user
        list_id = kwargs['list_id']
        if not user.is_authenticated():
            raise PermissionDenied
        if user.is_superuser:
            return fn(*args, **kwargs)
        if not hasattr(user, 'is_list_owner'):
            mlist = List.objects.get_or_404(fqdn_listname=list_id)
            user.is_list_owner = user_is_in_list_roster(user, mlist, "owners")
        if user.is_list_owner:
            return fn(*args, **kwargs)
        else:
            raise PermissionDenied
    return wrapper


def list_moderator_required(fn):
    """Check if the logged in user is a moderator of the given list.
    Assumes that the request object is the first arg and that list_id
    is present in kwargs.
    """
    def wrapper(*args, **kwargs):
        user = args[0].user
        list_id = kwargs['list_id']
        if not user.is_authenticated():
            raise PermissionDenied
        if user.is_superuser:
            return fn(*args, **kwargs)
        if (not hasattr(user, 'is_list_owner')
            or not hasattr(user, 'is_list_moderator')):
            mlist = List.objects.get_or_404(fqdn_listname=list_id)
            if not hasattr(user, 'is_list_owner'):
                user.is_list_owner = user_is_in_list_roster(
                    user, mlist, "owners")
            if not hasattr(user, 'is_list_moderator'):
                user.is_list_moderator = user_is_in_list_roster(
                    user, mlist, "moderators")
        if user.is_list_owner or user.is_list_moderator:
            return fn(*args, **kwargs)
        else:
            raise PermissionDenied
    return wrapper


def superuser_or_403(fn):
    """Make sure that the logged in user is a superuser or otherwise raise
    PermissionDenied.
    Assumes the request object to be the first arg."""
    def wrapper(*args, **kwargs):
        user = args[0].user
        if not user.is_superuser:
            raise PermissionDenied
        return fn(*args, **kwargs)
    return wrapper


def loggedin_or_403(fn):
    """Make sure that the logged in user is not anonymous or otherwise raise
    PermissionDenied.
    Assumes the request object to be the first arg."""
    def wrapper(*args, **kwargs):
        user = args[0].user
        if not user.is_authenticated():
            raise PermissionDenied
        return fn(*args, **kwargs)
    return wrapper
