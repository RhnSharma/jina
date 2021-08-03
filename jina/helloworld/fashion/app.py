import os
import shutil
from pathlib import Path

from jina import Flow
from jina.parsers.helloworld import set_hw_parser
# do `pip install git+https://github.com/jina-ai/executors.git@fix-pea-id-runtime`
from jinahub.indexers.storage.PostgreSQLStorage import PostgreSQLStorage
from jinahub.indexers.searcher.AnnoySearcher import AnnoySearcher

if __name__ == '__main__':
    from helper import (
        print_result,
        write_html,
        download_data,
        index_generator,
        query_generator,
    )
    from my_executors import MyEncoder, MyIndexer, MyEvaluator, MyConverter, MatchMerger
else:
    from .helper import (
        print_result,
        write_html,
        download_data,
        index_generator,
        query_generator,
    )
    from .my_executors import MyEncoder, MyIndexer, MyEvaluator, MyConverter

cur_dir = os.path.dirname(os.path.abspath(__file__))


def hello_world(args):
    """
    Runs Jina's Hello World.

    Usage:
        Use it via CLI :command:`jina hello-world`.

    Description:
        It downloads Fashion-MNIST dataset and :term:`Indexer<indexes>` 50,000 images.
        The index is stored into 4 *shards*. It randomly samples 128 unseen images as :term:`Queries<Searching>`
        Results are shown in a webpage.

    More options can be found in :command:`jina hello-world --help`

    :param args: Argparse object
    """

    Path(args.workdir).mkdir(parents=True, exist_ok=True)

    targets = {
        'index-labels': {
            'url': args.index_labels_url,
            'filename': os.path.join(args.workdir, 'index-labels'),
        },
        'query-labels': {
            'url': args.query_labels_url,
            'filename': os.path.join(args.workdir, 'query-labels'),
        },
        'index': {
            'url': args.index_data_url,
            'filename': os.path.join(args.workdir, 'index-original'),
        },
        'query': {
            'url': args.query_data_url,
            'filename': os.path.join(args.workdir, 'query-original'),
        },
    }

    # download the data
    download_data(targets, args.download_proxy)

    # reduce the network load by using `fp16`, or even `uint8`
    os.environ['JINA_ARRAY_QUANT'] = 'fp16'
    # now comes the real work
    # load index flow from a YAML file
    storage_flow = (
        Flow()
        .add(uses=MyEncoder, parallel=2)
        # requires PSQL running. do `docker run -e POSTGRES_PASSWORD=123456  -p 127.0.0.1:5432:5432/tcp postgres:13.2`
        .add(uses=PostgreSQLStorage, name='psql')
    )

    # store the data
    with storage_flow:
        storage_flow.index(
            index_generator(num_docs=targets['index']['data'].shape[0], target=targets),
            request_size=args.request_size,
            show_progress=True,
        )
        dump_path = os.path.join(os.path.curdir, 'dump')
        # if exists from previous run
        shutil.rmtree(dump_path, ignore_errors=True)
        # dump to intermediary location
        storage_flow.post(
            target_peapod='psql', # optional. just to avoid errors in the Encoder
            on='/dump',
            parameters={'dump_path': dump_path, 'shards': 2}
        )

    # define query flow
    query_flow = (
        Flow()
        .add(uses=MyEncoder, parallel=2)
        # to perform vector similarity
        # replicas >= 2 required for rolling update
        .add(uses=AnnoySearcher, name='searcher', parallel=2, replicas=2, uses_after=MatchMerger)
        # to retrieve full Document metadata
        .add(uses=PostgreSQLStorage, uses_with={'default_traversal_paths': ['m']})
        .add(uses=MyEvaluator)
    )

    # start query flow
    with query_flow:
        # perform rolling update
        query_flow.rolling_update(pod_name='searcher', dump_path=dump_path)

        # do a search
        query_flow.post(
            # can be `/eval`, but requires re-mapping requests. this is an MVP
            '/search',
            query_generator(
                num_docs=10, target=targets, with_groundtruth=True
            ),
            shuffle=True,
            on_done=print_result,
            request_size=args.request_size,
            parameters={'top_k': args.top_k},
            show_progress=True,
        )

        # write result to html
        write_html(os.path.join(args.workdir, 'demo.html'))


if __name__ == '__main__':
    args = set_hw_parser().parse_args()
    hello_world(args)
