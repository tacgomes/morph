# Copyright (C) 2011-2012  Codethink Limited
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


import cliapp
import collections
import logging
import os
import time
import warnings

import morphlib


defaults = {
    'repo-alias': [
        ('upstream='
            'git://git.baserock.org/delta/#'
            'ssh://gitano@git.baserock.org/delta/'),
        ('baserock='
            'git://git.baserock.org/baserock/#'
            'ssh://gitano@git.baserock.org/baserock/'),
        ('freedesktop='
            'git://anongit.freedesktop.org/#'
            'ssh://git.freedesktop.org/'),
        ('gnome='
            'git://git.gnome.org/%s#'
            'ssh://git.gnome.org/git/%s'),
        ('github='
            'git://github.com/%s#'
            'ssh://git@github.com/%s'),
    ],
    'cachedir': os.path.expanduser('~/.cache/morph'),
    'max-jobs': morphlib.util.make_concurrency(),
    'prefix': '/usr',
    'toolchain-target': '%s-baserock-linux-gnu' % os.uname()[4],
    'ccache-remotedir': '',
    'ccache-remotenlevels': 2,
    'build-ref-prefix': 'baserock/builds'
}


class Morph(cliapp.Application):

    def add_settings(self):
        self.settings.boolean(['verbose', 'v'],
                              'show what is happening in much detail')
        self.settings.boolean(['quiet', 'q'],
                              'show no output unless there is an error')
        self.settings.string_list(['repo-alias'],
                                  'define URL prefix aliases to allow '
                                  'repository addresses to be shortened; '
                                  'use alias=pullpattern=pushpattern '
                                  'to allow alias:shortname to be used '
                                  'instead of the full URL; the patterns must '
                                  'contain a %s where the shortname gets '
                                  'replaced',
                                  default=defaults['repo-alias'])
        self.settings.string(['bundle-server'],
                             'base URL to download bundles',
                             metavar='URL',
                             default=None)
        self.settings.string(['cache-server'],
                             'HTTP URL of the morph cache server to use',
                             metavar='URL',
                             default=None)
        self.settings.string(['cachedir'],
                             'put build results in DIR',
                             metavar='DIR',
                             default=defaults['cachedir'])
        self.settings.string(['prefix'],
                             'build chunks with prefix PREFIX',
                             metavar='PREFIX', default=defaults['prefix'])
        self.settings.string(['toolchain-target'],
                             'set the TOOLCHAIN_TARGET variable which is used '
                             'in some chunks to determine which architecture '
                             'to build tools for',
                             metavar='TOOLCHAIN_TARGET',
                             default=defaults['toolchain-target'])
        self.settings.string(['target-cflags'],
                             'inject additional CFLAGS into the environment '
                             'that is used to build chunks',
                             metavar='CFLAGS',
                             default='')
        self.settings.string(['tempdir'],
                             'temporary directory to use for builds '
                             '(this is separate from just setting $TMPDIR '
                             'or /tmp because those are used internally '
                             'by things that cannot be on NFS, but '
                             'this setting can point at a directory in '
                             'NFS)',
                             metavar='DIR',
                             default=os.environ.get('TMPDIR'))
        self.settings.boolean(['no-ccache'], 'do not use ccache')
        self.settings.string(['ccache-remotedir'],
                             'allow ccache to download objects from REMOTEDIR '
                             'if they are not cached locally',
                             metavar='REMOTEDIR',
                             default=defaults['ccache-remotedir'])
        self.settings.integer(['ccache-remotenlevels'],
                              'assume ccache directory objects are split into '
                              'NLEVELS levels of subdirectories',
                              metavar='NLEVELS',
                              default=defaults['ccache-remotenlevels'])
        self.settings.boolean(['no-distcc'], 'do not use distcc')
        self.settings.integer(['max-jobs'],
                              'run at most N parallel jobs with make (default '
                              'is to a value based on the number of CPUs '
                              'in the machine running morph',
                              metavar='N',
                              default=defaults['max-jobs'])
        self.settings.boolean(['keep-path'],
                              'do not touch the PATH environment variable')
        self.settings.boolean(['bootstrap'],
                              'build stuff in bootstrap mode; this is '
                              'DANGEROUS and will install stuff on your '
                              'system')
        self.settings.boolean(['ignore-submodules'],
                              'do not cache repositories of git submodules '
                              'or unpack them into the build directory')

        self.settings.boolean(['no-git-update'],
                              'do not update the cached git repositories '
                              'during a build (user must have done that '
                              'already using the update-gits subcommand)')

        self.settings.string_list(['staging-filler'],
                                  'unpack BLOB into staging area for '
                                  'non-bootstrap builds (this will '
                                  'eventually be replaced with proper '
                                  'build dependencies)',
                                  metavar='BLOB')
        self.settings.boolean(['staging-chroot'],
                              'build things in a staging chroot '
                              '(require real root to use)')

        self.settings.string(['build-ref-prefix'],
                             'Prefix to use for temporary build refs',
                             metavar='PREFIX',
                             default=defaults['build-ref-prefix'])

    def setup_plugin_manager(self):
        cliapp.Application.setup_plugin_manager(self)

        self.pluginmgr.locations += os.path.join(
            os.path.dirname(morphlib.__file__), 'plugins')

        s = os.environ.get('MORPH_PLUGIN_PATH', '')
        self.pluginmgr.locations += s.split(':')

        self.hookmgr = cliapp.HookManager()
        self.hookmgr.new('new-build-command', cliapp.FilterHook())
        self.system_kind_builder_factory = \
            morphlib.builder2.SystemKindBuilderFactory()

    def itertriplets(self, args):
        '''Generate repo, ref, filename triples from args.'''

        if (len(args) % 3) != 0:
            raise cliapp.AppException('Argument list must have full triplets')

        while args:
            assert len(args) >= 2, args
            yield args[0], args[1], args[2]
            args = args[3:]

    def _itertriplets(self, *args):
        warnings.warn('_itertriplets is deprecated, '
                      'use itertriplets instead', stacklevel=1,
                      category=DeprecationWarning)
        return self.itertriplets(*args)

    def create_source_pool(self, lrc, rrc, triplet):
        pool = morphlib.sourcepool.SourcePool()

        def add_to_pool(reponame, ref, filename, absref, tree, morphology):
            source = morphlib.source.Source(reponame, ref, absref, tree,
                                            morphology, filename)
            pool.add(source)

        self.traverse_morphs([triplet], lrc, rrc,
                             update=not self.settings['no-git-update'],
                             visit=add_to_pool)
        return pool

    def _create_source_pool(self, *args):
        warnings.warn('_create_source_pool is deprecated, '
                      'use create_source_pool instead', stacklevel=1,
                      category=DeprecationWarning)
        return self.create_source_pool(*args)

    def _resolveref(self, lrc, rrc, reponame, ref, update=True):
        '''Resolves commit and tree sha1s of the ref in a repo and returns it.

        If update is True then this has the side-effect of updating
        or cloning the repository into the local repo cache.

        '''
        absref = None
        if lrc.has_repo(reponame):
            repo = lrc.get_repo(reponame)
            if update:
                self.status(msg='Updating cached git repository %(reponame)s',
                            reponame=reponame)
                repo.update()
            absref, tree = repo.resolve_ref(ref)
        elif rrc is not None:
            try:
                absref, tree = rrc.resolve_ref(reponame, ref)
            except:
                pass
        if absref is None:
            if update:
                self.status(msg='Caching git repository %(reponame)s',
                            reponame=reponame)
                repo = lrc.cache_repo(reponame)
                repo.update()
            else:
                repo = lrc.get_repo(reponame)
            absref, tree = repo.resolve_ref(ref)
        return absref, tree

    def traverse_morphs(self, triplets, lrc, rrc, update=True,
                        visit=lambda rn, rf, fn, arf, m: None):
        morph_factory = morphlib.morphologyfactory.MorphologyFactory(lrc, rrc)
        queue = collections.deque(triplets)

        while queue:
            reponame, ref, filename = queue.popleft()
            absref, tree = self._resolveref(lrc, rrc, reponame, ref, update)
            morphology = morph_factory.get_morphology(
                reponame, absref, filename)
            visit(reponame, ref, filename, absref, tree, morphology)
            if morphology['kind'] == 'system':
                queue.extend((s['repo'], s['ref'], '%s.morph' % s['morph'])
                             for s in morphology['strata'])
            elif morphology['kind'] == 'stratum':
                if morphology['build-depends']:
                    queue.extend((s['repo'], s['ref'], '%s.morph' % s['morph'])
                                 for s in morphology['build-depends'])
                queue.extend((c['repo'], c['ref'], '%s.morph' % c['morph'])
                             for c in morphology['chunks'])

    def _traverse_morphs(self, *args):
        warnings.warn('_traverse_morphs is deprecated, '
                      'use traverse_morphs instead', stacklevel=1,
                      category=DeprecationWarning)
        return self.traverse_morphs(*args)

    def cache_repo_and_submodules(self, cache, url, ref, done):
        subs_to_process = set()
        subs_to_process.add((url, ref))
        while subs_to_process:
            url, ref = subs_to_process.pop()
            done.add((url, ref))
            cached_repo = cache.cache_repo(url)
            cached_repo.update()

            try:
                submodules = morphlib.git.Submodules(self, cached_repo.path,
                                                     ref)
                submodules.load()
            except morphlib.git.NoModulesFileError:
                pass
            else:
                for submod in submodules:
                    if (submod.url, submod.commit) not in done:
                        subs_to_process.add((submod.url, submod.commit))

    def _cache_repo_and_submodules(self, *args):
        warnings.warn('_cache_repo_and_submodules is deprecated, '
                      'use cache_repo_and_submodules instead', stacklevel=1,
                      category=DeprecationWarning)
        return self.cache_repo_and_submodules(*args)

    def status(self, **kwargs):
        '''Show user a status update.

        The keyword arguments are formatted and presented to the user in
        a pleasing manner. Some keywords are special:

        * ``msg`` is the message text; it can use ``%(foo)s`` to embed the
          value of keyword argument ``foo``
        * ``chatty`` should be true when the message is only informative,
          and only useful for users who want to know everything (--verbose)
        * ``error`` should be true when it is an error message

        All other keywords are ignored unless embedded in ``msg``.

        '''

        assert 'msg' in kwargs
        text = kwargs['msg'] % kwargs

        error = kwargs.get('error', False)
        chatty = kwargs.get('chatty', False)
        quiet = self.settings['quiet']
        verbose = self.settings['verbose']

        if error:
            logging.error(text)
        elif chatty:
            logging.debug(text)
        else:
            logging.info(text)

        ok = verbose or error or (not quiet and not chatty)
        if ok:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
            self.output.write('%s %s\n' % (timestamp, text))
            self.output.flush()

    def runcmd(self, argv, *args, **kwargs):
        if 'env' not in kwargs:
            kwargs['env'] = dict(os.environ)

        # convert the command line arguments into a string
        commands = [argv] + list(args)
        for command in commands:
            if isinstance(command, list):
                for i in xrange(0, len(command)):
                    command[i] = str(command[i])
        commands = [' '.join(command) for command in commands]

        # print the command line
        self.status(msg='# %(cmdline)s',
                    cmdline=' | '.join(commands),
                    chatty=True)

        # Log the environment.
        for name in kwargs['env']:
            logging.debug('environment: %s=%s' % (name, kwargs['env'][name]))

        # run the command line
        return cliapp.Application.runcmd(self, argv, *args, **kwargs)
