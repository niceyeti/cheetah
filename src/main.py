


"""
TODO:
	0) Lint
	1) Other algorithms, share regression, visualization, 
	2) Test scripts
	3) Design: based on dependencies, how can code be broken up? Currently this mixes top-level user input/output with analyses, models, etc
"""

import sys
sys.path.append('./common')
sys.path.append('./util')

import os
import harvard_persist
from datetime import datetime
from common import cheetah
from common import cheetah_present
from harvard_loader import getHeadlinesFromHarvardCsv
from result_collection import ResultCollection
from data_transformer import DataTransformer
from zipfile import ZipFile
from util.fasttext_downloader import FastTextDownloader

dataDir = "../data/"
reproDir = "../repro/"
modelDir = "../models/"
resultDir = "../results/"
lexicaDir = "../lexica/"
licensePath = "../license.md"
logoDir = "../misc/logos"


def printLicense():
	"""
	
	"""
	with open(licensePath, "r") as licenseFile:
		print(licenseFile.read())

def getTopics():
	return input("Enter target topic terms, separated by commas: ").lower().split(",")

def listFiles(dirPath, extension="", verbose=True):
	# Lists files in DirPath by name, with optional extension filter.
	fList = [fname for fname in os.listdir(dirPath) if fname.endswith(extension)]
	fList = sorted(fList)
	if verbose:
		print("Found {} files in {} with {} extension:".format(len(fList), dirPath, extension))
		print("  ".join(["{}. {}\n".format(i,fname) for i, fname in enumerate(fList)]))
	return fList

def unzipReproData(reproFname="cheetah_repro.zip"):
	"""
	Unzips a filename in @reproFolder to @dataDir under a folder of the file's same name, e.g.
	'cheetah_repro.zip' will be unzipped to ../data/cheetah_repro.
	If the output folder already exists, the unzip is aborted to prevent overwriting.
	@reproFname: The output folder to which dataset will be unzipped
	"""
	zipPaths = [os.path.join(reproDir,fname) for fname in listFiles(reproDir, ".zip") if reproFname in fname]
	if zipPaths:
		print("HERE")
		zipPath = zipPaths[0]
		outputFolder = reproFname.replace(".zip","")
		odir = os.path.join(dataDir, outputFolder)
		if os.path.exists(odir):
			print("WARNING: the output folder {} already exists. Data unzip aborted. Delete output folder and retry.".format(odir))
			return
		with ZipFile(zipPath, "r") as zipFile:
			print("Unzipping {}. Files in zipped repro:".format(zipPath))
			zipFile.printdir()
			zipFile.extractall(path=odir)

def selectOption(validOptions, prompt="Select option: "):
	#Returns selected option as str
	#@validOptions: must be a list of strings
	option = input(prompt)
	while option not in validOptions:
		print("Invalid option. Re-enter.")
		option = input(prompt)
	return option

def selectFromFileList(flist, prompt="File list"):
	# Select a file from the provided list, and return its name
	print(prompt)
	print("\t"+"\t".join(["{}: ".format(i)+fname+"\n" for i, fname in enumerate(flist)]).rstrip())
	options = [str(i) for i in range(len(flist))]
	selectedOption = selectOption(options)
	selectedIndex = int(selectedOption)
	return flist[selectedIndex]

def selectDataFile(jsonDir):
	# Select a file by name in some directory
	jsonPaths = [path for path in listFiles(jsonDir, "json", verbose=False) if "filtered" in path ]
	jsonPath = selectFromFileList(jsonPaths, prompt="Select a repro dataset: ")
	return os.path.join(jsonDir,jsonPath)

def downloadEnglishModel():
	# One-shot, downloads English text model. This could support listing, selecting, and downloading instead, but not needed now.
	modelSource = "https://fasttext.cc/docs/en/crawl-vectors.html"
	print("English word vector model will be downloaded from "+modelSource)
	print("These models are quite large (>2Gb) which can take an hour or more to download on slow connections.")
	print("Alternatively, use a browser to manually download models to the models/[language] folder from "+modelSource)
	confirmation = input("Do you wish to proceed? Enter y or n: ").lower() in ["y", "yes"]
	if confirmation:
		ftd = FastTextDownloader()
		ftd.download(["english"], modelVersion="text", destFolder=modelDir)

def loadDataset():
	cheetahFolder = "cheetah_repro"
	cheetahDir = os.path.join(dataDir, cheetahFolder)
	# unzip cheetah_repro.zip file if not already unzipped to ../data/cheetah_repro/
	if not os.path.exists(cheetahDir):
		print("Unzipping dataset to "+cheetahFolder)
		unzipReproData(cheetahFolder)
	else:
		print("Dataset already unzipped to "+cheetahFolder+". Proceeding to dataset selection.")
	jsonPath = selectDataFile(cheetahDir)
	return ResultCollection.LoadCollections(jsonPath)

def loadStopWordLexicon():
	stopPath = os.path.join(lexicaDir, "stop/stopwords.txt")
	stopLex = cheetah.Lexicon(stopPath)
	stopLex.Words = DataTransformer.TextNormalizeTerms(stopLex.Words, filterNonAlphaNum=True, deleteFiltered=False, lowercase=True)
	return stopLex

def loadSentimentLexicon(sentFolder):
	lexicon = cheetah.SentimentLexicon(sentFolder)
	lexicon.Positives = DataTransformer.TextNormalizeTerms(lexicon.Positives, filterNonAlphaNum=True, deleteFiltered=False, lowercase=True)
	lexicon.Negatives = DataTransformer.TextNormalizeTerms(lexicon.Negatives, filterNonAlphaNum=True, deleteFiltered=False, lowercase=True)
	return lexicon

def loadFastTextModel():
	modelPath = os.path.join(modelDir, "english/cc.en.300.vec")
	if not os.path.exists(modelPath):
		print("ERROR: model not found at {}. Select 'Download fasttext model' in main menu to download model before running analysis.".format(modelPath))
		return
	return cheetah.loadFastTextModel(modelPath=modelPath)

def runCheetah(resultCollections):
	topicLists = [result.Topics for collection in resultCollections for result in collection.QueryResults]
	print("Topic lists: "+str(topicLists))
	vectorModel = loadFastTextModel()
	sentFolder = os.path.join(lexicaDir, "sentiment/my_gensim/")
	topicCrossFilter = True
	removeOffTopicTerms = True
	uniquify = False
	dtLow, dtHigh = ResultCollection.GetMinMaxDt(resultCollections)
	DataTransformer.PrimaryResultCollectionFilter(resultCollections, dtLow.date(), dtHigh.date(), topicCrossFilter, removeOffTopicTerms, uniquify)

	stopLex = loadStopWordLexicon()
	DataTransformer.RemoveStopWords(resultCollections, stopLex.Words)

	lexicon = loadSentimentLexicon(sentFolder)
	for topics in topicLists:
		lexicon.removeTerms(topics)

	cheetah_present.cheetahSentimentAnalysis( \
		resultCollections, \
		lexicon, \
		vectorModel, \
		dtLow.date(), \
		dtHigh.date(), \
		dtGrouping="weekly", \
		resultFolder=resultDir, \
		useScoreWeight=False, \
		useSoftMatch=False,
		normalizeScores=False)

def harvardAnalyzeAndPersist():
	opath = dataDir+"stories_election_web_cheetofied.csv"
	csvPath = dataDir+"stories_election_web.csv"

	if os.path.isfile(opath):
		print("Output path already exists, and must be moved or deleted before running: {}".format(opath))
		return	
	if not os.path.isfile(csvPath):
		print("Csv path not found: {}".format(csvPath))
		print("First download harvard {} data and place it or a link of the same name in {} folder.".format(csvPath, dataDir))
		return
	print("Running cheetah on harvard data and persisting to {}".format(opath))

	model = loadFastTextModel()
	sentFolder = os.path.join(lexicaDir, "sentiment/my_gensim/")
	sentLex = loadSentimentLexicon(sentFolder)
	stopLex = loadStopWordLexicon()
	csvTransformer = harvard_persist.HarvardCsvCheetahVisitor(model, sentLex, stopLex)
	csvTransformer.cheetifyHarvardCsv(csvPath, opath)

def harvardAnalysis():
	csvPath = dataDir+"stories_election_web.csv"
	if not os.path.isfile(csvPath):
		print("Csv path not found: {}".format(csvPath))
		print("First download harvard stories_election_web.csv data and place it or a link of the same name in the data/ folder.")
		return

	#TODO: manual user input, organization partitioning
	#get topic terms from the user (multiple lists)
	#topics = getTopics()
	#get date range: dtLow, dtHigh
	#load multiple results
	#for topicList in topicLists:
	#load the first topic's headlines

	trumpTopics = ["trump", "trumps", "donald", "donalds"]
	clintonTopics = ["hillary", "hillarys", "clinton", "clintons"]
	topicLists = [trumpTopics, clintonTopics]
	year = 2016

	headlines = getHeadlinesFromHarvardCsv(csvPath, year, topicLists[0])
	resultCollection = ResultCollection.FromResult(headlines, topicLists[0], "harvard")
	#load the rest
	for topicTerms in topicLists[1:]:
		headlines = getHeadlinesFromHarvardCsv(csvPath, year, topicTerms)
		resultCollection.AddResult(topicTerms, headlines)

	print("Result collection contains:")
	for result in resultCollection.QueryResults:
		print("{} headlines on {}".format(len(result.Headlines), result.Topics))

	runCheetah([resultCollection])

def cheetahAbleAnalysis():
	"""
	-Select and load a dataset
	-Run cheetah, outputting to results/ folder
	"""
	runCheetah(loadDataset())

def modelAnalysis():
	"""
	Analyze a model's sentiment bias wrt some input topics.
	"""	
	modelPath=os.path.join(modelDir, "english/cc.en.300.vec")
	if not os.path.exists(modelPath):
		print("ERROR: model not found at {}. Select 'Download fasttext model' in main menu to download model before running analysis.".format(modelPath))
		return
	vectorModel = cheetah.loadFastTextModel(modelPath=modelPath)
	sentFolder = os.path.join(lexicaDir, "sentiment/my_gensim/")
	quit = False
	while not quit:
		queryTerms = input("Enter query terms, separated by commas. Or 'quit' to exit: ")
		queryTerms = [q for q in queryTerms.lower().split(",") if len(q) > 0]
		quit = "quit" in queryTerms
		if not quit:
			print("Query: "+str(queryTerms))
			topicalSentiment = cheetah.netAlgebraicSentimentWrapper(queryTerms, sentFolder, vectorModel, avgByHits=True)
			print("{} net sentiment: {}".format(queryTerms,topicalSentiment))

def printLogo():
	logoPaths = [os.path.join(logoDir,logoPath) for logoPath in os.listdir(logoDir)]
	logoPath = logoPaths[datetime.now().second % len(logoPaths)]
	with open(logoPath, "r") as logoFile:
		print(logoFile.read())

def printIntro():
	desc = """

                   ________  _______________________    __  __
                  / ____/ / / / ____/ ____/_  __/   |  / / / /
                 / /   / /_/ / __/ / __/   / / / /| | / /_/ / 
                / /___/ __  / /___/ /___  / / / ___ |/ __  /  
                \____/_/ /_/_____/_____/ /_/ /_/  |_/_/ /_/  


                           Never trust--only verify.


Welcome to Cheetah, a cousin of the ABLE-ITEM deep web content extractor and Sentinel analysis
engine. I am an American NLP developer and informatic security researcher specializing in the 
use of nlp and deep learning for counter-misinformation. The purpose of this tool is to provide
live-demos of open source multi-language misinformation analysis methods. Also some other (and
perhaps funner) nlp stuff too. This basic interface is primarily for algorithmic/dataset repro purposes.


To execute cheetah repro, begin by downloading the fasttext english '.text' model (option 0).
Then run Cheetah analysis (options 1 and 2).
"""
	"""
Upcoming analyses:
1) Vector model algebraic analysis: analyzing the prior bias built into vector space language
	models due to input data bias.
2) Vector/document clustering and 3d visualization
3) Attempts at share regression:
		Problem: "Map language vectors D to facebook/twitter/other social share counts."
    This is a fascinating and useful topic for analyzing the value of specific topics with respect
	to positive/negative sentiment. The approach allows us to correlate the value of 
	misinformation to different content platforms and organizations, to understand the economic
	incentives of bias and misinformation for different organizations. Put simply, you can regress
	on share/engagement counts to evaluate and compare the value of bias/topics for a website or
	any other content source.
4) Russian, Chinese, and other global analyses:
	Problem: How do sentiment dynamics, topical polarization generalize to other regions/regimes?
5) Lexicon generation: how generating signal lexica in any language is a snap.
6) Structured inference: given the distribution of search results returned by a biased search
	platform (e.g. Google/Youtube, Chinese-censored platforms, etc), learn the sentiment
	parameters of its output. This is simple transfer learning where given a set of ranked results
	for some query, you use a structured perceptron and doc-vectors to reproduce the same
	algorithm. One algorithm learns the other's behavior through learning-to-rank. By doing so, you
	can evaluate the biases of search algorithms as misinformation actors fiddle with their
	parameters to obtain some target behavior.

Cheers.
"""
	print(desc)

def mainMenu():

	printLogo()
	printIntro()

	cmdDict = {
		"0": downloadEnglishModel,
		"1": cheetahAbleAnalysis,
		"2": harvardAnalysis,
		"3": harvardAnalyzeAndPersist,
		"4": modelAnalysis,
		"5": printIntro,
		"6": printLicense,
		"7": exit
	}

	while True:
		print("Main menu")
		print("\t0) Download English FastText model")
		print("\t1) Cheetah analyis--ABLE")
		print("\t2) Cheetah analysis--Harvard Shorenstein")
		print("\t3) Analyze and persist Harvard data with cheetah (Warning: 48h+ runtime!)")
		print("\t4) Model analysis")
		print("\t5) Intro")
		print("\t6) License info")
		print("\t7) Exit")
		option = selectOption(cmdDict.keys())
		cmd = cmdDict[option]
		cmd()

def main():
	mainMenu()

if __name__ == "__main__":
	main()
